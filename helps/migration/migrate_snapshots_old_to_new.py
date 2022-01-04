""" 
    These must be ran locally.

    Migrate volume snapshots from EKS cluster in one account/region to another.
    
    python migrate_snapshots_old_to_new.py \
        --old_aws_profile_name osl-e
        --old_eks_cluster_name osl-daac-cluster
        --old_aws_region us-east-1
        --new_aws_profile_name osl-e-west
        --new_eks_cluster_name osl-daac-test-cluster
        --new_aws_region us-west-2
        --billing_tag_key osl-billing
        --billing_tag_value osl-daac-test
"""
import argparse
import time

import boto3
import colorama

parser = argparse.ArgumentParser()
parser.add_argument("--old_aws_profile_name")
parser.add_argument("--old_eks_cluster_name")
parser.add_argument("--old_aws_region")
parser.add_argument("--new_aws_profile_name")
parser.add_argument("--new_eks_cluster_name")
parser.add_argument("--new_aws_region")
parser.add_argument("--billing_tag_key")
parser.add_argument("--billing_tag_value")

args = parser.parse_args()

old_profile = args.old_aws_profile_name
old_cluster = args.old_eks_cluster_name
old_region = args.old_aws_region

new_profile = args.new_aws_profile_name
new_cluster = args.new_eks_cluster_name
new_region = args.new_aws_region
billing_tag_key = args.billing_tag_key
billing_tag_value = args.billing_tag_value

colorama.init(autoreset=True)

old_session = boto3.Session(profile_name=old_profile)
new_session = boto3.Session(profile_name=new_profile)

old_ec2 = old_session.client('ec2')
new_ec2 = new_session.client('ec2')

old_account_number = old_session.client('sts').get_caller_identity().get('Account')  # 553778890976
new_account_number = new_session.client('sts').get_caller_identity().get('Account')  # 701288258305

old_snaps = old_ec2.describe_snapshots(
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
old_snaps = old_snaps['Snapshots']

for i, snap in enumerate(old_snaps):
    try:
        # Get snapshot tags and ids
        old_snap_id = snap['SnapshotId']
        old_tags = snap['Tags']
        old_vol_size = snap['VolumeSize']

        print(colorama.Fore.GREEN + f"\n\n{i+1} ****** Trying '{old_snap_id}' with vol '{old_vol_size}'")
        
        # Replace cluster name with new cluster name.
        new_tags = []
        for tag in old_tags:
            if tag['Key'] == 'kubernetes.io/cluster/{cluster_name}'.format(cluster_name=old_cluster):
                new_tags.append({'Key': 'kubernetes.io/cluster/{cluster_name}'.format(cluster_name=new_cluster), 'Value': 'owned'})
            elif 'aws:' in tag['Key'] :
                continue
            elif 'dlm:' in tag['Key']:
                continue
            elif 'osl-stackname' in tag['Key']:
                continue
            elif 'hub-db-dir' in tag['Value']:
                continue
            else:
                new_tags.append(tag)
        
        new_tags.append(
            {
                'Key':'OldAccountSnapshotId',
                'Value': str(old_snap_id)
            }
        )

        new_tags.append({
                'Key': str(billing_tag_key),
                'Value': str(billing_tag_value)
            }
        )

        print(new_tags)

        # Modify permissions of snapshot and ADD NEW ACCOUNT NUMBER, as needed
        #response = old_ec2.modify_snapshot_attribute(
        #    Attribute='createVolumePermission',
        #    OperationType='add',
        #    SnapshotId=old_snap_id,
        #    UserIds=[
        #        new_account_number,
        #    ]
        #)

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
                    'Values': [old_snap_id]
                }
            ],
            OwnerIds=['self']
        )

        if new_snap['Snapshots']:
            if new_snap['Snapshots'][0]['State'] == 'error':
                raise Exception( f"The snapshot state is {new_snap['Snapshots'][0]['StateMessage']} for {new_snap['Snapshots'][0]}")

        if len(new_snap['Snapshots']) == 0:
            try:
                response = new_ec2.copy_snapshot(
                    SourceRegion=old_region,
                    SourceSnapshotId=old_snap_id,
                    TagSpecifications=[
                        {
                            'ResourceType': 'snapshot',
                            'Tags': new_tags
                        },
                    ]
                )
                print(f"Snapshot '{old_snap_id}' copied to new account.")
            except new_ec2.exceptions.ClientError as e:
                print("Too many pending snapshots. Wait for 1 minute and continue.")
                time.sleep(60)
        else:
            print(f"Snapshot '{old_snap_id}' already found in new account.")
    
    except Exception as e:
        print(colorama.Fore.RED + f"Something went wrong with {i+1}.... {e}")
