"""

# test
python force_pass_start.py \
    --aws_profile_name osl-e-west \
    --cognito_userpool_id us-west-2_o4F8Kassa \
    --preauth_lambda_function_arn arn:aws:lambda:us-west-2:701288258305:function:osl-daac-test-cognito-PreAuthFunction-fksPtHlhJSjj
"""

import json
import argparse

import boto3
import colorama

parser = argparse.ArgumentParser()
parser.add_argument("--aws_profile_name")
parser.add_argument("--cognito_userpool_id")
parser.add_argument("--preauth_lambda_function_arn")
args = parser.parse_args()

profile = args.aws_profile_name
userpool_id = args.cognito_userpool_id
lambda_function_arn = args.preauth_lambda_function_arn

colorama.init(autoreset=True)

session = boto3.Session(profile_name=profile)

cog = session.client('cognito-idp')
lamb = session.client('lambda')

# Get list of users in old account
response = cog.list_users(
    UserPoolId=userpool_id
)

for dumb in range(1200):

    try:
        next_token = response['PaginationToken']
    except:
        next_token = None

    for i, user in enumerate(response['Users']):

        username = user['Username']
        user_status = user['UserStatus']  
        email_verified = "false"

        all_attributes = user['Attributes']
        for att in all_attributes:
            if att['Name'] == 'email_verified':
                email_verified = att['Value']

        try:
            if user_status == 'FORCE_CHANGE_PASSWORD':
                print(colorama.Fore.GREEN + f"\n\n{dumb+1}.{i+1}. Invoking lambda for user '{username}'.")

                event = {
                    "userPoolId": userpool_id, 
                    "userName": username, 
                    "request": {
                        "userAttributes": {
                            "cognito:user_status": user_status, 
                            "email_verified": email_verified
                        }
                    }
                }

                response = lamb.invoke(
                    FunctionName=lambda_function_arn,
                    InvocationType='Event',
                    LogType='None',
                    Payload=bytes(json.dumps(event), "utf-8")
                )
                
            else:
                print(colorama.Fore.MAGENTA + f"User '{username}' already is Confirmed. Skipping lambda invoke...")

        except Exception as e:
            print(colorama.Fore.RED + f"Something went wrong with... {e}")

    try:
        #print(f"Using next page token: {next_token}")
        response = cog.list_users(
            UserPoolId=userpool_id,
            PaginationToken=next_token
        )
    except:
        print(f"No more pagination at batch {dumb}. Exiting...")
        exit()
