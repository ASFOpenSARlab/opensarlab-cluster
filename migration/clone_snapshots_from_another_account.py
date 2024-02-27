#!/usr/bin/env python3

######
#
# Clone snapshots from another account.
# The snapshots must be visible from the account. This might require changing permissions on the snapshot.
# Meant to be run in cloudshell of the particular region/account where the proper environment varibles are set.
#
######

import time
import json

import boto3


def _get_tag_value(tags, tag_key: str) -> str:
    val = [s["Value"] for s in tags if s["Key"] == tag_key]

    if not val:
        val = [""]

    return str(val[0])


def main(args):
    # Initialize Boto3
    session = boto3.Session()
    ec2 = session.client("ec2")

    sts = boto3.client("sts")
    new_account_id = sts.get_caller_identity()["Account"]

    old_account_json = None

    # Open JSON and get snapshot metadata
    with open("new_tags.json", "r") as f:
        old_account_json = json.load(f)

    for snap_id, new_tags in old_account_json.items():
        response = ec2.describe_snapshots(
            SnapshotIds=[snap_id], OwnerIds=[args["old_account_id"]]
        )

        snap_from_old_account = response["Snapshots"][0]
        snap_claim_name = _get_tag_value(new_tags, "kubernetes.io/created-for/pvc/name")

        ## If this account has snapshot already by tags, skip
        response = ec2.describe_snapshots(
            Filters=[
                {
                    "Name": f"tag:kubernetes.io/cluster/{args['new_cluster_name']}",
                    "Values": ["owned"],
                },
                {"Name": f"tag:from-{args['old_cluster_name']}", "Values": ["true"]},
                {
                    "Name": f"tag:kubernetes.io/created-for/pvc/name",
                    "Values": [f"{snap_claim_name}"],
                },
            ],
            OwnerIds=["self"],
        )

        if response["Snapshots"][0]["AccountId"] == new_account_id:
            print(f"Snapshot found already for {snap_claim_name}")
            continue

        try:
            response = ec2.copy_snapshot(
                SourceRegion=args["old_region_name"],
                SourceSnapshotId=snap_from_old_account["SnapshotId"],
                TagSpecifications=[
                    {"ResourceType": "snapshot", "Tags": new_tags},
                ],
                DryRun=False,
            )
            print(
                f"Snapshot '{snap_from_old_account['snapshotId']}' copied to new account."
            )

        except ec2.exceptions.ClientError as e:
            print(e)
            if e.response["Error"]["Code"] == "DryRunOperation":
                break

            print("Too many pending snapshots. Wait for 1 minute and continue.")
            time.sleep(60)


if __name__ == "__main__":
    args = {
        "old_cluster_name": "smce-test-cluster",
        "old_account_id": "233535791844",
        "new_cluster_name": "smce-prod-cluster",
        "old_region_name": "us-west-2",
    }

    main(args)
