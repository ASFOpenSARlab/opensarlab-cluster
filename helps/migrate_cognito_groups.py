""" These must be ran locally. Do not forget to update the config settings """

import boto3
import botocore
import colorama

############ Config Settings #####

old_profile = 'jupyterhub'
old_cluster = 'opensarlab'
old_region = 'us-east-1'
old_userpool_id = 'us-east-1_SRN0dZC66'

new_profile = 'osl-e'
new_cluster = 'osl-daac-cluster'
new_region = 'us-east-1'
new_userpool_id = 'us-east-1_bw1NialdW'

##################################

colorama.init(autoreset=True)

old_session = boto3.Session(profile_name=old_profile)
new_session = boto3.Session(profile_name=new_profile)

old_cog = old_session.client("cognito-idp")
new_cog = new_session.client("cognito-idp")

# Get groups in old
res1 = old_cog.list_groups(UserPoolId=old_userpool_id)

for group in res1['Groups']:
    group_name = group['GroupName']
    print(f"Creating group '{group_name}' in new account.")
    
    try:
        prec = group['Precedence']
    except:
        prec = 0

    try:
        desc = group['Description']
    except:
        desc = ''
    

    try:
        res2 = new_cog.create_group(
            GroupName=group_name,
            UserPoolId=new_userpool_id,
            Description=desc,
            Precedence=prec
        )
    except new_cog.exceptions.GroupExistsException as e:
        print("Group already exists in new account. Skipping creation...")

    # Get users in old groups
    res3 = old_cog.list_users_in_group(
        UserPoolId=old_userpool_id,
        GroupName=group_name
    )

    for user in res3['Users']:
        username = user['Username']

        try:
            response = new_cog.admin_add_user_to_group(
                UserPoolId=new_userpool_id,
                Username=username,
                GroupName=group_name
            )
        except new_cog.exceptions.UserNotFoundException as e:
            print("User not found ")
