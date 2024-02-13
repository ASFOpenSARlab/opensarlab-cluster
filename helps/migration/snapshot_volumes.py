#!/usr/bin/env python3

######
#
# Take snapshots of user volumes and make sure they have the right tags.
# Meant to be run in cloudshell of the particular region/account where the proper environment varibles are set.
#
# > snapshot_volumes.py
#
######

import argparse

import boto3

def main(args):

    cluster_name = args.get('cluster')
    
    # Initialize Boto3
    session = boto3.Session()
    ec2 = session.client('ec2')

    # Get list of volumes belonging to particular cluster
    volumes = ec2.describe_volumes(
        Filters=[
            {
                'Name': 'tag:kubernetes.io/cluster/{cluster_name}'.format(cluster_name=cluster_name),
                'Values': ['owned']
            },
        ]
    )

    volumes = volumes['Volumes']

    if len(volumes) > 0:

        # Take snapshots of each volume. Make sure the tags are copied over.
        for vol in volumes:

            # tags = [{'Key': 'string','Value': 'string'},]
            tags = []

            response = ec2.create_snapshot(
                VolumeId=vol['VolumeId'],
                TagSpecifications=[
                    {
                        'ResourceType': 'snapshot',
                        'Tags': tags
                    },
                ],
                DryRun=False
            )

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--cluster', help='Name of eks cluster the volumes belong to.')
    args = parser.parse_args()

    main(args)
