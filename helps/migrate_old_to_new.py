""" These must be ran locally. Do not forget to update the config settings """

import boto3
import botocore
import colorama

############ Config Settings #####

migrate_users = False
migrate_snapshots = True

"""
old_profile = 'jupyterhub'
old_cluster = 'opensarlab-test'
old_region = 'us-east-1'
old_userpool_id = 'us-east-1_no7VRWUuB'
"""

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

if migrate_snapshots:
    old_ec2 = old_session.client('ec2')
    new_ec2 = new_session.client('ec2')

    old_account_number = old_session.client('sts').get_caller_identity().get('Account')  # 553778890976
    new_account_number = new_session.client('sts').get_caller_identity().get('Account')  # 701288258305

    old_snap = old_ec2.describe_snapshots(
            Filters=[
                {
                    'Name': 'tag:kubernetes.io/cluster/{cluster_name}'.format(cluster_name=old_cluster),
                    'Values': ['owned']
                },
                {
                    'Name': 'status',
                    'Values': ['completed']
                }
            ],
            OwnerIds=['self']
        )
    old_snaps = old_snap['Snapshots']
    import pdb; pdb.set_trace()
    for i, snap in enumerate(old_snaps):

        try:
            # Get snapshot tags and ids
            snap_id = snap['SnapshotId']
            tags = snap['Tags']
            vol_size = snap['VolumeSize']

            print(colorama.Fore.GREEN + f"\n\n{i+1} ****** Trying '{snap_id}'")
            #print(tags)
            if snap_id != 'snap-0b390605330381997':
                continue
            else:
                print(" claim-boukamass ")

            exit()
            
            # Replace cluster name with new cluster name.
            new_tags = []
            for tag in tags:
                if tag['Key'] == 'kubernetes.io/cluster/{cluster_name}'.format(cluster_name=old_cluster):
                    new_tags.append({'Key': 'kubernetes.io/cluster/{cluster_name}'.format(cluster_name=new_cluster), 'Value': 'owned'})
                elif 'aws:' in tag['Key'] :
                    continue
                elif 'dlm:' in tag['Key']:
                    continue
                else:
                    new_tags.append(tag)
            
            new_tags.append({'Key':'OldAccountSnapshotId', 'Value': snap_id})

            print(new_tags)

            # Modify permissions of snapshot and add new account number, as needed
            response = old_ec2.modify_snapshot_attribute(
                Attribute='createVolumePermission',
                OperationType='add',
                SnapshotId=snap_id,
                UserIds=[
                    new_account_number,
                ]
            )

            # Copy (old, private) snapshot into new account, if needed. Make sure tags are up-to-date.
            new_snap = new_ec2.describe_snapshots(
                Filters=[
                    {
                        'Name': 'tag:kubernetes.io/cluster/{cluster_name}'.format(cluster_name=new_cluster),
                        'Values': ['owned']
                    },
                    {
                        'Name': 'status',
                        'Values': ['completed', 'pending', 'error']
                    },
                    {
                        'Name': 'tag:OldAccountSnapshotId',
                        'Values': [snap_id]
                    }
                ],
                OwnerIds=['self']
            )    

            if not new_snap['Snapshots']:
                response = new_ec2.copy_snapshot(
                    SourceRegion=new_region,
                    SourceSnapshotId=snap_id,
                    TagSpecifications=[
                        {
                            'ResourceType': 'snapshot',
                            'Tags': new_tags
                        },
                    ]
                )
                print(f"Snapshot '{snap_id}' copied to new account.")
            else:
                print(f"Snapshot '{snap_id}' already found in new account.")
        
        except Exception as e:
            print(colorama.Fore.RED + f"Something went wrong with {i}.... {e}")

if migrate_users:
    old_cog = old_session.client('cognito-idp')
    new_cog = new_session.client('cognito-idp')

    # Get list of users in old account
    response = old_cog.list_users(
        UserPoolId=old_userpool_id
    )
    print(response)

    for dumb in range(1200):

        try:
            next_token = response['PaginationToken']
        except:
            next_token = None

        for i, user in enumerate(response['Users']):

            username = user['Username']
            all_attributes = user['Attributes']

            # Remove attributes that are unmutable
            attributes = []
            for att in all_attributes:
                if att['Name'] == 'sub':
                    continue
                else:
                    attributes.append(att)

            print(colorama.Fore.GREEN + f"\n\n{dumb+1}.{i+1}. Creating user '{username}' with attributes '{attributes}'.")

            try:
                try:
                    user_exists = new_cog.admin_get_user(
                        UserPoolId=new_userpool_id,
                        Username=username
                    )
                except new_cog.exceptions.UserNotFoundException as e:
                    print(f"User '{username}' not found in new account. Creating user...")

                    response = new_cog.admin_create_user(
                        UserPoolId=new_userpool_id,
                        Username=username,
                        UserAttributes=attributes,
                        MessageAction='SUPPRESS'
                    )
                else:
                    print(colorama.Fore.MAGENTA + f"User '{username}' already exists in new account. Skipping user creation.")

            except Exception as e:
                print(colorama.Fore.RED + f"Something went wrong with... {e}")

        try:
            print(f"Using next page token: {next_token}")
            response = old_cog.list_users(
                UserPoolId=old_userpool_id,
                PaginationToken=next_token
            )
            print(response)
        except:
            print(f"No more pagination at batch {dumb}. Exiting...")
            exit()
