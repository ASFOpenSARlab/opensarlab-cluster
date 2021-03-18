import json
import os 
import boto3
from botocore.exceptions import ClientError

def send_email(email, env):

    print("Sending email of form: ")
    print(email)

    # Create a new SES resource and specify a region.
    client = boto3.client('ses', region_name=env['region_name'])
    
    # Try to send the email.
    try:
        #Provide the contents of the email.
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    email['RECIPIENT'],
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': "UTF-8",
                        'Data': email['BODY_HTML'],
                    },
                    'Text': {
                        'Charset': "UTF-8",
                        'Data': "",
                    },
                },
                'Subject': {
                    'Charset': "UTF-8",
                    'Data': email['SUBJECT'],
                },
            },
            Source=email['SENDER']
        )
    # Display an error if something goes wrong.	
    except ClientError as e:
        print("Something went wrong in sending email.")
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])
        
def email_reset(userName, userEmail, fullName, env):
    
    """
    # Replace sender@example.com with your "From" address.
    # This address must be verified with Amazon SES.
    SENDER = "Sender Name <sender@example.com>"
    
    # Replace recipient@example.com with a "To" address. If your account 
    # is still in the sandbox, this address must be verified.
    RECIPIENT = "recipient@example.com"
    """
    
    # Send email to Jupyter Group 
    email_meta = {
        'SENDER': '{adminEmailAddress}'.format(adminEmailAddress=env['admin_email_address']), 
        'RECIPIENT': "OSL Admin <{adminEmailAddress}>".format(adminEmailAddress=env['admin_email_address']),
        'SUBJECT': "User Password Reset",
        'BODY_HTML': """<html>
            <head></head>
            <body>
                <p>{fullName} ({userName}) at {userEmail} just reset their password for access to {clusterDomain}. No admin action is required at this time.</p>
            </body>
            </html>""".format(userName=userName, userEmail=userEmail, fullName=fullName, clusterDomain=env['cluster_domain'], adminEmailAddress=env['admin_email_address']) 
    }
    
    send_email(email_meta, env)
    
def email_signup(userName, userEmail, fullName, env):
    
    """
    # Replace sender@example.com with your "From" address.
    # This address must be verified with Amazon SES.
    SENDER = "Sender Name <sender@example.com>"
    
    # Replace recipient@example.com with a "To" address. If your account 
    # is still in the sandbox, this address must be verified.
    RECIPIENT = "recipient@example.com"
    """
    
    # Send email to Jupyter Group 
    email_meta = {
        'SENDER': '{adminEmailAddress}'.format(adminEmailAddress=env['admin_email_address']), 
        'RECIPIENT': "OSL Admin <{adminEmailAddress}>".format(adminEmailAddress=env['admin_email_address']),
        'SUBJECT': "OSL User Signup",
        'BODY_HTML': """<html>
            <head></head>
            <body>
                <p>{fullName} ({userName}) at {userEmail} just signed up for access to {clusterDomain}. Please verify and <i>enable</i> their account.</p>
            </body>
            </html>""".format(userName=userName, userEmail=userEmail, fullName=fullName, clusterDomain=env['cluster_domain'], adminEmailAddress=env['admin_email_address']) 
    }

    send_email(email_meta, env)
    
    # Send email to user
    email_meta = {
        'SENDER': "{adminEmailAddress}".format(adminEmailAddress=env['admin_email_address']),
        'RECIPIENT': '"{fullName}" <{userEmail}>'.format(fullName=fullName, userEmail=userEmail),
        'SUBJECT': "OSL Account Access Pending",
        'BODY_HTML': """<html>
            <head></head>
            <body>
                <p>
                You recently have applied for access to {clusterDomain} operated by the Alaska Satellite Facility (ASF). 
                You are using the username '{userName}'. 
                This email confirms that your email is verified.  
                </p>
                <p>
                To complete the process, ASF must review your account before confirmation.
                You will be contacted via email if there are questions about your account.
                If there are no questions, you will be notified via email when your account has been confirmed.
                Confirmation may take up to a day. 
                </p>
            </body>
            </html>""".format(userName=userName, clusterDomain=env['cluster_domain'], adminEmailAddress=env['admin_email_address'])
    }
    
    send_email(email_meta, env)
     
def lambda_handler(event, context):

    env = {
        "region_name": os.environ['region_name'],
        "stackname": os.environ['stackname'],
        "cluster_domain": os.environ['cluster_domain'],
        "admin_email_address": os.environ['admin_email_address']
    }
    
    print(f"Email handling function for cluster {env['stackname']}")
    print(event)
    
    # If resetting password, don't disable.
    if event['triggerSource'] == 'PostConfirmation_ConfirmForgotPassword':
        email_reset(event['userName'], event['request']['userAttributes']['email'], event['request']['userAttributes']['name'], env)
    
    # If signing up, disable for admin confirmation
    elif event['triggerSource'] == 'PostConfirmation_ConfirmSignUp':
        client = boto3.client('cognito-idp')
        response = client.admin_disable_user(
            UserPoolId=event['userPoolId'],
            Username=event['userName']
        )
    
        print(response)
    
        email_signup(event['userName'], event['request']['userAttributes']['email'], event['request']['userAttributes']['name'], env)
    
    return event