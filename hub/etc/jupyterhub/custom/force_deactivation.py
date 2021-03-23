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

        session = boto3.Session(region_name=meta['region_name'])
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

        self._all_cog_users = self._get_user_list()

        self.force_group_name = 'force_deactivation'

    def _get_user_list(self):
        res = self.cognito.list_users(
                UserPoolId=self.cognito.user_pool_id,
                Limit=60
            )
        user_list = [u['Username'] for u in res['Users']]
        token = res.get('PaginationToken', None)

        while token:
            res = self.cognito.list_users(
                UserPoolId=self.cognito.user_pool_id,
                Limit=60, 
                PaginationToken=token
            )
            user_list.extend([u['Username'] for u in res['Users']])
            token = res.get('PaginationToken', None)
            
            if not token:
                break
        
        print(f"{len(user_list)} Cognito users found")
        return user_list

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

        user_list = [u for u in self._all_cog_users if username == u.lower()]
        if len(user_list) == 0:
            raise Exception(f"Username {username} not found in Cognito")

        elif len(user_list) >= 2:
            raise Exception(f"Username '{username}' matches more than one cognito name: {user_list}")

        else:
            print(f"Username '{username}' matches cognito name '{user_list[0]}'")
            return user_list[0] 

    def get_names_in_group(self):
        users = self.g.get_users_in_group(self.force_group_name)

        # Convert users to pvc_names
        names = [(f"claim-{escapism.escape(u.name, escape_char='-')}", u) for u in users]

        return names

    def delete_volume(self, pvc_name):
        if not self.dry_run:
            print(f"Deleting pvc_name {pvc_name}")
            self.api.delete_namespaced_persistent_volume_claim(body=k8s_client.V1DeleteOptions(), name=pvc_name, namespace=self.namespace)
        else:
            print(f"Dry run: Did not delete pvc (and volume) for {pvc_name}")

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
        else:
            print(f"No snapshots found for {pvc_name}")

    def disable_cog_user(self, userObj):
        cog_username = self._get_cog_username(userObj.name)
        if cog_username:
            if not self.dry_run:
                #https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cognito-idp.html#CognitoIdentityProvider.Client.admin_disable_user
                res = self.cognito.admin_disable_user(
                    UserPoolId=self.cognito.user_pool_id,
                    Username=cog_username
                )

                print(f"Disabled Cognito user {cog_username}")
            else:
                print(f"Dry run: Did not disable Cognito user {cog_username}.")

    def remove_osl_user(self, userObj):
        if not self.dry_run:
            self.session.delete(userObj)
            self.session.commit()
            print(f"User {userObj.name} deleted from OSL DB")
        else:
            print(f"Dry run: Did not delete user {userObj.name} from OSL DB")

def deactivate(cluster='opensarlab', dry_run=False):
    try:
        ds = Deactivate(cluster, dry_run)

        names = ds.get_names_in_group()

        print(f"Found {len(names)} users belonging to group '{ds.force_group_name}'")

        for pvc_name, userObj in names:
            try:
                ds.disable_cog_user(userObj)
                ds.remove_osl_user(userObj)
                ds.delete_volume(pvc_name)
                ds.delete_snapshot(pvc_name)
            except Exception as e:
                print(f"There was an error: {e}. Skipping to next name...")

    except Exception as e:
        print(e)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster", default="opensarlab")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    args = parser.parse_args()

    deactivate(args.cluster, args.dry_run)
