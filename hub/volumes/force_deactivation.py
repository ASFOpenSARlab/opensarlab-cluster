#!/usr/bin/env python3

import os
import datetime
import urllib
import time
import argparse

import escapism
import yaml
import boto3
from botocore.exceptions import ClientError
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException


class Deactivate():

    def __init__(self, cluster=None, dry_run=True):
        print("Checking for expired snapshots...")

        with open("/etc/jupyterhub/custom/meta.yaml", 'r') as f:
            data = f.read()

        meta = yaml.safe_load(data)

        session = boto3.Session(aws_secret_access_key=meta['aws_secret_access_key'], aws_access_key_id=meta['aws_access_key_id'], region_name=meta['region_name'])
        self.cluster_name = meta['cluster_name']
        print(f"Cluster name set to {self.cluster_name}")

        # List of threshold days since last activity.
        # On all but the last day an email is sent out warning about deletion of data and user deactivation.
        # On the last day, users are deactivated and user data is deleted.
        self.days_since_activity_thresholds = [30,37,41,43,45,46]

        print(f"Dry run set to {dry_run}")
        self.dry_run = dry_run

        self.cognito = session.client('cognito-idp')
        user_pools = self.cognito.list_user_pools(MaxResults=10)
        pool_id = [ u['Id'] for u in user_pools['UserPools'] if u['Name'] == self.cluster_name ][0]
        if not pool_id:
            raise Exception(f"Cognito user Pool '{self.cluster_name}' does not exist.")
        self.cognito.user_pool_id = pool_id

        self.ec2 = session.client('ec2')

        self.ses = session.client('ses')

        self.all_cog_users = self._get_user_list()

        os.environ['KUBERNETES_SERVICE_PORT'] = meta['kubernetes_service_port']
        os.environ['KUBERNETES_SERVICE_HOST'] = meta['kubernetes_service_host']

        self.namespace = meta['namespace']

        k8s_config.load_incluster_config()
        self.api = k8s_client.CoreV1Api()
        
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

    def _get_cog_username(self, username):

        user_list = [u for u in self.all_cog_users if username == u.lower()]
        if len(user_list) == 0:
            raise Exception(f"Username {username} not found in Cognito")

        elif len(user_list) >= 2:
            raise Exception(f"Username '{username}' matches more than one cognito name: {user_list}")

        else:
            print(f"Username '{username}' matches cognito name '{user_list[0]}'")
            return user_list[0] 

    def _get_username(self, snapshot):

        pvc_name = self._get_tags(snapshot, 'kubernetes.io/created-for/pvc/name')
        if len(pvc_name) == 0:
            raise Exception(f"Something went wrong with getting username for {snapshot['Tags']}")
        username = pvc_name[0].replace('claim-', '')
        if username == 'hub-db-dir':
            print("Database volume found. Do not delete. Skipping...")
            return

        # 'escapism' is the custom library used by JupyterHub to escape server names
        username = escapism.unescape(username, escape_char='-')

        return username

    def _disable_user(self, username):
        if not self.dry_run:
        
            cog_username = self._get_cog_username(username)

            if cog_username:
                #https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cognito-idp.html#CognitoIdentityProvider.Client.admin_disable_user
                res = self.cognito.admin_disable_user(
                    UserPoolId=self.cognito.user_pool_id,
                    Username=cog_username
                )

                print(f"Disabled user {cog_username}: {res}")
        else:
            print(f"Dry run: Did not disable user {cog_username}.")

    def get_snapshots(self):

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
                    'Values': ['*']
                }, 
                {
                    'Name': 'tag:forced-deactivation',
                    'Values': ['*']
                }
            ],
            OwnerIds=['self']
        )
        return snap['Snapshots']

    def delete_snapshots_and_user(self, snaps):

        if len(snaps) > 0:
            for snap in snaps:
                if not self.dry_run:
                    if self._get_tags(snap, 'do-not-delete'):
                        print("Do-not-delete tag found. Skipping...")
                    else:
                        print(f"**** Deleting {snap['SnapshotId']}")
                        self.ec2.delete_snapshot(SnapshotId=snap['SnapshotId'], DryRun=False)

                        username = self._get_username(snap)
                        self._disable_user(username)
                else:
                    print(f"Dry run: Did not delete snapshot {snap['SnapshotId']}") 

    def get_volumes(self):

        vols = self.ec2.describe_volumes(
            Filters=[
                {
                    'Name': 'tag:kubernetes.io/cluster/{0}'.format(self.cluster_name),
                    'Values': ['owned']
                },
                {
                    'Name': 'tag:kubernetes.io/created-for/pvc/name',
                    'Values': ['*']
                },
                {
                    'Name': 'status',
                    'Values': ['available']
                }, 
                {
                    'Name': 'tag:forced-deactivation',
                    'Values': ['*']
                }
            ]
        )

        vols = vols['Volumes']

        print(f"Number of vols: {len(vols)}")
        if len(vols) == 0:
            vols = []

        return vols

    def delete_volumes(self, volumes):
        for vol in volumes:
            pvc_name = self._get_tags(vol, 'kubernetes.io/created-for/pvc/name')
            self.api.delete_namespaced_persistent_volume_claim(body=k8s_client.V1DeleteOptions(), name=pvc_name, namespace=self.namespace)

def deactivate(cluster='opensarlab', dry_run=False):
    try:
        ds = Deactivate(cluster, dry_run)

        vols = ds.get_volumes()
        ds.delete_volumes(vols)

        snaps = ds.get_snapshots()
        ds.delete_snapshots_and_user(snaps)

    except Exception as e:
        print(e)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster", default="opensarlab")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    args = parser.parse_args()

    deactivate(args.cluster, args.dry_run)
