
"""
Write to file list of user emails from Cognito filtered by days since EC2 tag jupyter-volume-stopping-time

Using EC2 snapshot usage as a proxy for activity, get all user's emails from userpool `cognito_userpool_id` and within a 
certain time period `max_days_since_last_used` for the cluster `eks_cluster_name`.


python get_emails.py \
    --eks_cluster_name osl-daac-cluster \
    --aws_profile_name osl-e \
    --cognito_userpool_id us-east-1_bw1NialdW \
    --max_days_since_last_used 46

"""

import os
import datetime
import argparse

import boto3
import escapism
import colorama

colorama.init(autoreset=True)

parser = argparse.ArgumentParser()
parser.add_argument("--eks_cluster_name")
parser.add_argument("--aws_profile_name")
parser.add_argument("--cognito_userpool_id")
parser.add_argument("--max_days_since_last_used", default=46)
args = parser.parse_args()

cluster_name = args.eks_cluster_name
profile_name = args.aws_profile_name
cognito_userpool_id = args.cognito_userpool_id
max_days_since_last_used = args.max_days_since_last_used

class BadTagsException(Exception):
    """
    If tags are not expected.
    """

class BadAttributesException(Exception):
    """
    If attributes are not expected.
    """

session = boto3.Session(profile_name=profile_name)

cognito = session.client('cognito-idp')
ec2 = session.client('ec2')

def get_tag_value(tags, key):
    value = None
    for tag in tags:
        if tag['Key'] == key:
            value = tag['Value']
            break

    if not value:
        raise BadTagsException(f"No matching tags {key}")

    return value

def get_user_attribute(attributes, name):
        value = None
        for att in attributes:
            if att['Name'] == name:
                value = att['Value']
                break

        if not value:
            raise BadAttributesException(f"No matching {name}")

        return value

def get_enabled_users_with_emails():
        res = cognito.list_users(
                UserPoolId=cognito_userpool_id,
                Limit=60
            )
        user_list = [
            (u['Username'], get_user_attribute(u['Attributes'], 'email'))
            for u in res['Users']
            if u['Enabled'] is True and u['UserStatus'] == 'CONFIRMED'
            ]
        token = res.get('PaginationToken', None)

        while token:
            res = cognito.list_users(
                UserPoolId=cognito_userpool_id,
                Limit=60,
                PaginationToken=token
            )
            user_list.extend([
                (u['Username'], get_user_attribute(u['Attributes'], 'email'))
                for u in res['Users']
                if u['Enabled'] is True and u['UserStatus'] == 'CONFIRMED'
                ])
            token = res.get('PaginationToken', None)

            if not token:
                break

        return user_list

print("Getting snapshots...")

# Get usernames of all users active within time period
snapshots = ec2.describe_snapshots(
            Filters=[
                {
                    'Name': 'tag:kubernetes.io/cluster/{cluster_name}'.format(cluster_name=cluster_name),
                    'Values': ['owned']
                },
                {
                    'Name': 'status',
                    'Values': ['completed']
                }
            ],
            OwnerIds=['self']
        )

active_usernames = []

snapshots = snapshots['Snapshots']

num_snapshots = len(snapshots)
print(f"Number of snapshots found: {num_snapshots}")

for i, snap in enumerate(snapshots):

    try:
        snapshot_id = snap['SnapshotId']

        print(colorama.Fore.GREEN + f"{i}/{num_snapshots}. Checking snapshot '{snapshot_id}'...")

        tags = snap['Tags']

        claim_name = get_tag_value(tags, 'kubernetes.io/created-for/pvc/name')  # claim-hello
        stopping_time = get_tag_value(tags, 'jupyter-volume-stopping-time')  # 2020-01-10 01:00:52.648872

        username = claim_name.split("claim-")[1]

        try:
            username_esc = escapism.unescape(username, escape_char='-')
        except Exception as e:
            print(colorama.Fore.RED + f"Escaping username {username} failed: {e}. Skipping to next...")
            continue

        last_stopped = datetime.datetime.strptime(stopping_time, '%Y-%m-%d %H:%M:%S.%f')
        now = datetime.datetime.now()

        if (now - last_stopped).days <= max_days_since_last_used:
            active_usernames.append(username_esc)

    except BadTagsException as e:
        print(colorama.Fore.RED + str(e))

print(f"Possible number of active usernames to be emailed (based on snapshot activity): {len(active_usernames)}")

# Get emails from username list
print("Get all active users with emails.")
all_enabled_users_with_emails = get_enabled_users_with_emails()
print(f"Number of enabled users with confirmed emails: {len(all_enabled_users_with_emails)}")

print("Writing to file...")
with open("emails_to_send.csv", "w") as f:
    for username, email in all_enabled_users_with_emails:
        if username in active_usernames:
            f.write(f"{username},{email}\n")
