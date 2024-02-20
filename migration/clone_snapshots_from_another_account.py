#!/usr/bin/env python3

######
#
# Clone snapshots from another account.
# The snapshots must be visible from the account. This might require changing permissions on the snapshot.
# Meant to be run in cloudshell of the particular region/account where the proper environment varibles are set.
#
######

import time

import boto3


def main(args):
    # Initialize Boto3
    session = boto3.Session()
    ec2 = session.client("ec2")

    if args["specific_user_claim"]:
        # Get specfic snapshot of a particular user (if it exists)
        response = ec2.describe_snapshots(
            Filters=[
                {
                    "Name": f"tag:kubernetes.io/cluster/{args['new_cluster_name']}",
                    "Values": ["owned"],
                },
                {"Name": "status", "Values": ["completed", "pending", "error"]},
                {"Name": f"tag:from-{args['old_cluster_name']}", "Values": "true"},
                {
                    "Name": f"tag:kubernetes.io/created-for/pvc/name",
                    "Values": [f"{args['specific_user_claim']}"],
                },
            ],
            OwnerIds=["self"],
        )

    else:
        # Get list of all snapshots belonging to particular cluster
        response = ec2.describe_snapshots(
            Filters=[
                {
                    "Name": f"tag:kubernetes.io/cluster/{args['new_cluster_name']}",
                    "Values": ["owned"],
                },
                {"Name": "status", "Values": ["completed", "pending", "error"]},
                {"Name": f"tag:from-{args['old_cluster_name']}", "Values": "true"},
                {
                    "Name": f"tag:kubernetes.io/created-for/pvc/name",
                    "Values": f"args['specific_user_claim']",
                },
            ],
            OwnerIds=["self"],
        )

    snapshots = response["Snapshots"]

    if len(snapshots) == 0:
        print("No snapshots found")

    if len(snapshots) > 0:
        for snap in snapshots:
            print(f"Cloning volume: {snap}]\n\n")

            try:
                response = ec2.copy_snapshot(
                    SourceRegion=args["old_region_name"],
                    SourceSnapshotId=snap["snapshotId"],
                    TagSpecifications=[
                        {"ResourceType": "snapshot", "Tags": snap["Tags"]},
                    ],
                    DryRun=True,
                )
                print(f"Snapshot '{snap['snapshotId']}' copied to new account.")

            except ec2.exceptions.ClientError:
                print("Too many pending snapshots. Wait for 1 minute and continue.")
                time.sleep(60)
            except ec2.meta.client.exceptions.DryRunOperation:
                print("Dry Run Operation has all necessary permissions")


if __name__ == "__main__":
    args = {
        "old_cluster_name": "smce-test-cluster",
        "new_cluster_name": "smce-prod-cluster",
        "old_region_name": "us-west-2",
        "specific_user_claim": "claim-emlundell",
    }

    main(args)
