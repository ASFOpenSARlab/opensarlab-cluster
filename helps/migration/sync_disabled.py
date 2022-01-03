""" These must be ran locally.

    Sync disable status of AWS Cognito users from one userpool into another. 
    Users need to be present in the new account already. 

    python sync_disabled.py \
        --old_aws_profile_name osl-e
        --old_cognito_userpool_id us-east-1_bw1NialdW
        --new_aws_profile_name osl-e-west
        --new_cognito_userpool_id us-west-2_o4F8Kassa
"""

import argparse

import boto3
import colorama

parser = argparse.ArgumentParser()
parser.add_argument("--old_aws_profile_name")
parser.add_argument("--old_cognito_userpool_id")
parser.add_argument("--new_aws_profile_name")
parser.add_argument("--new_cognito_userpool_id")
args = parser.parse_args()

old_profile = args.old_aws_profile_name
old_userpool_id = args.old_cognito_userpool_id

new_profile = args.new_aws_profile_name
new_userpool_id = args.new_cognito_userpool_id

colorama.init(autoreset=True)

old_session = boto3.Session(profile_name=old_profile)
new_session = boto3.Session(profile_name=new_profile)

old_cog = old_session.client('cognito-idp')
new_cog = new_session.client('cognito-idp')

# Get list of users in old account
response = old_cog.list_users(
    UserPoolId=old_userpool_id
)

for dumb in range(1200):

    try:
        next_token = response['PaginationToken']
    except:
        next_token = None

    for i, user in enumerate(response['Users']):

        username = user['Username']
        is_enabled = user['Enabled']

        try:
            if not is_enabled:
                try:
                    print(colorama.Fore.GREEN + f"\n\n{dumb+1}.{i+1}. Setting user '{username}' to 'not enabled' in new account.")
                    response = new_cog.admin_disable_user(
                        UserPoolId=new_userpool_id,
                        Username=username
                    )

                except new_cog.exceptions.UserNotFoundException as e:
                    print(colorama.Fore.RED + f"New account user '{username}' not found. Skipping...")

                except Exception as e:
                    print(colorama.Fore.RED + f"New account user '{username}' could not be updated. Skipping...")
            else:
                print(colorama.Fore.MAGENTA + f"User '{username}' enabled in new account. Skipping...")

        except Exception as e:
            print(colorama.Fore.RED + f"Something went wrong with... {e}")

    try:
        response = old_cog.list_users(
            UserPoolId=old_userpool_id,
            PaginationToken=next_token
        )
    except:
        print(f"No more pagination at batch {dumb}. Exiting...")
        exit()
