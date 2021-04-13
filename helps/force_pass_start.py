import json

import boto3
import botocore
import colorama

############ Config Settings #####

profile = 'osl-e'
userpool_id = 'us-east-1_bw1NialdW'
lambda_function_arn = 'arn:aws:lambda:us-east-1:701288258305:function:osl-daac-auth-PreAuthFunction-18XY6TKIZZNSV'

##################################

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
