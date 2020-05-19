#!/usr/bin/env python3

# The purpose of this script is to create some group tables and migrate user groups from Cognito
# This should be ran within the hub pod
"""
from jupyterhub import groups

g = groups.Groups()
g.add_group('general_cpu')
g.get_users_in_group('general_cpu')
g.add_user_to_group('emlundell_test1', 'general_cpu')
g.get_users_in_group('general_cpu')
"""

import boto3
from jupyterhub import groups
from jupyterhub import orm

def all_osl_users():
    users_obj = self.session.query(orm.User).all()
    users = [u.name for u in users_obj]
    return users

def cognito_users_by_group(group_name):
    with open("from_cognito.conf", "r") as f:
        conf = f.read()

    session = boto3.Session(aws_secret_access_key=conf['aws_secret_access_key', aws_access_key_id=conf['aws_access_key_id'], region_name=conf['region_name'])
    client = session.client('cognito-idp')

    response = client.list_users_in_group(
        UserPoolId=conf['user_pool_id'],
        GroupName=group_name,
    )

    return [u['Username'] for u in list_users['Users']]

g = groups.Groups()

# Create default group `general_cpu` action and make default initalize for all
try:
    g.add_group('general_cpu')

    users = cognito_users_by_group('general_cpu')
    for user in users:
        g.add_user_to_group(user, 'general_cpu')
except Exception as e:
    print(e)

# Create empty `sudo` action group
try:
    g.add_group('sudo')
except Exception as e:
    print(e)

# Create empty `general_gpu` action group
try:
    g.add_group('general_gpu')
except Exception as e:
    print(e)

# Create `NISAR Science Team` label group and populate with certain users
try:
    g.add_group('NISAR Science Team')

    users = cognito_users_by_group('NISAR')
    for user in users:
        g.add_user_to_group(user, 'NISAR Science Team')
except Exception as e:
    print(e)
