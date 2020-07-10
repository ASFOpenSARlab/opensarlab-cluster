#!/usr/bin/env python3

"""
Remove any disabled Cognito users from the OSL users DB table.

Any active Cognito users are ignored. 
Any OSL users that are not in Cognito are ignored.
Only disabled Cognito users are removed from the DB table.
"""

import boto3
import yaml

class RemoveDisabled():

    def __init__(self, meta):

        with open("/etc/jupyterhub/custom/meta.yaml", 'r') as f:
            data = f.read()

        meta = yaml.safe_load(data)

        session = boto3.Session(aws_secret_access_key=meta['aws_secret_access_key'], aws_access_key_id=meta['aws_access_key_id'], region_name=meta['region_name'])
        self.cluster_name = meta['cluster_name']
        print(f"Cluster name set to {self.cluster_name}")

        self.cognito = session.client('cognito-idp')
        user_pools = self.cognito.list_user_pools(MaxResults=10)
        pool_id = [ u['Id'] for u in user_pools['UserPools'] if u['Name'] == self.cluster_name ][0]
        if not pool_id:
            raise Exception(f"Cognito user Pool '{self.cluster_name}' does not exist.")
        self.cognito.user_pool_id = pool_id

    def get_deactivated_users(self):
        res = self.cognito.list_users(
                UserPoolId=self.cognito.user_pool_id,
                Limit=60, 
                Filter='status = "Disabled"'
            )
        user_list = [u['Username'] for u in res['Users']]
        token = res.get('PaginationToken', None)

        while token:
            res = self.cognito.list_users(
                UserPoolId=self.cognito.user_pool_id,
                Limit=60, 
                Filter='status = "Disabled"',
                PaginationToken=token
            )
            user_list.extend([u['Username'] for u in res['Users']])
            token = res.get('PaginationToken', None)
            
            if not token:
                break
        
        print(f"{len(user_list)} Cognito users found")
        return user_list

    def remove_user_from_DB(self, user):
        # TODO:  
        pass

def remove_disabled(meta):

    rd = RemoveDisabled(meta)

    users = rd.get_deactivated_users()

    for user in users:
        rd.remove_user_from_DB(user)
