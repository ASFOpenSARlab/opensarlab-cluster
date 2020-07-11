#!/usr/bin/env python3
   
import os
import datetime
import urllib
import time
import argparse

from jupyterhub import groups
import escapism
import yaml
import boto3
from botocore.exceptions import ClientError
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

class Deactivate():

    def __init__(self, cluster=None, dry_run=True):
        with open("/etc/jupyterhub/custom/meta.yaml", 'r') as f:
            data = f.read()

        meta = yaml.safe_load(data)

        session = boto3.Session(aws_secret_access_key=meta['aws_secret_access_key'], aws_access_key_id=meta['aws_access_key_id'], region_name=meta['region_name'])
        self.cluster_name = meta['cluster_name']
        print(f"Cluster name set to {self.cluster_name}")

        print(f"Dry run set to {dry_run}")
        self.dry_run = dry_run

        self.cognito = session.client('cognito-idp')
        user_pools = self.cognito.list_user_pools(MaxResults=10)
        pool_id = [ u['Id'] for u in user_pools['UserPools'] if u['Name'] == self.cluster_name ][0]
        if not pool_id:
            raise Exception(f"Cognito user Pool '{self.cluster_name}' does not exist.")
        self.cognito.user_pool_id = pool_id

        self.ec2 = session.client('ec2')

        os.environ['KUBERNETES_SERVICE_PORT'] = meta['kubernetes_service_port']
        os.environ['KUBERNETES_SERVICE_HOST'] = meta['kubernetes_service_host']

        self.namespace = meta['namespace']

        k8s_config.load_incluster_config()
        self.api = k8s_client.CoreV1Api()

        self.g = groups.Groups()
        self.session = self.g.session 

    def _get_tags(self, snapshot, tag_key):
        return [v['Value'] for v in snapshot['Tags'] if v['Key'] == tag_key]

    def _get_snapshots(self, pvc_name):
        # Get snapshot
        snap = self.ec2.describe_snapshots(
            Filters=[
                {
                    'Name': 'tag:kubernetes.io/cluster/{0}'.format(self.cluster_name),
                    'Values': ['owned']
                },
                {
                    'Name': 'status',
                    'Values': ['completed']
                },
                {
                    'Name': 'tag:kubernetes.io/created-for/pvc/name',
                    'Values': [f'{pvc_name}']
                }
            ],
            OwnerIds=['self']
        )
        return snap['Snapshots']

    def _get_cog_username(self, username):

        user_list = [u for u in self.all_cog_users if username == u.lower()]
        if len(user_list) == 0:
            raise Exception(f"Username {username} not found in Cognito")

        elif len(user_list) >= 2:
            raise Exception(f"Username '{username}' matches more than one cognito name: {user_list}")

        else:
            print(f"Username '{username}' matches cognito name '{user_list[0]}'")
            return user_list[0] 

    def get_pvc_names_in_group(self):
        users = self.g.get_users_in_group('force-deactivate')

        # Convert users to pvc_names
        names = [(f"claim-{escapism.escape(u.name, escape_char='-')}", u) for u in users]

        return names

    def delete_volume(self, pvc_name):
        if not self.dry_run:
            print(f"Deleting pvc_name {pvc_name}")
            self.api.delete_namespaced_persistent_volume_claim(body=k8s_client.V1DeleteOptions(), name=pvc_name, namespace=self.namespace)
        else:
            print(f"Dry run: Did not delete pvc_name {pvc_name}")

    def delete_snapshot(self, pvc_name):
        snaps = self._get_snapshots(pvc_name)

        if len(snaps) > 0:
            for snap in snaps:
                if not self.dry_run:
                    if self._get_tags(snap, 'do-not-delete'):
                        print("Do-not-delete tag found. Skipping...")
                    else:
                        print(f"**** Deleting {snap['SnapshotId']}")
                        self.ec2.delete_snapshot(SnapshotId=snap['SnapshotId'], DryRun=False)
                else:
                    print(f"Dry run: Did not delete snapshot {snap['SnapshotId']}") 

    def disable_cog_user(self, user):
        cog_username = self._get_cog_username(user.name)
        if cog_username:
            if not self.dry_run:
                #https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cognito-idp.html#CognitoIdentityProvider.Client.admin_disable_user
                res = self.cognito.admin_disable_user(
                    UserPoolId=self.cognito.user_pool_id,
                    Username=cog_username
                )

                print(f"Disabled Cognito user {cog_username}: {res}")
            else:
                print(f"Dry run: Did not disable Cognito user {cog_username}.")

    def remove_osl_user(self, user):
        # Get User DB object
        userDB = ...
        self.session.delete(userDB)

def deactivate(cluster='opensarlab', dry_run=False):
    try:
        ds = Deactivate(cluster, dry_run)

        names = ds.get_pvc_names_in_group()

        for pvc_name, user in names:
            try:
                ds.delete_volume(pvc_name)
                ds.delete_snapshot(pvc_name)
                ds.disable_cog_user(user)
                ds.remove_osl_user(user)
            except Exception as e:
                print(f"There was an error: {e}")

    except Exception as e:
        print(e)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster", default="opensarlab")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    args = parser.parse_args()

    deactivate(args.cluster, args.dry_run)
