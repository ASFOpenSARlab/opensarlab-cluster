#!/usr/bin/env python3

######
#
# Clone snapshots from same account.
# TODO Update comment
# The script "take_snapshots_of_volumes_for_another_account" is used to take snapshots of volumes. However, this does not capture snapshots without accompying volumes that still need to be migrated.
# Meant to be run in cloudshell of the particular region/account where the proper environment varibles are set.
#
######

import boto3

import json
import time


def main(args):
    # Initialize Boto3
    session = boto3.Session()
    ec2 = session.client("ec2")

    if args["specific_user_claim"]:
        # Get specfic snapshot of a particular user (if it exists)
        response = ec2.describe_snapshots(
            Filters=[
                {
                    "Name": f"tag:kubernetes.io/cluster/{args['old_cluster_name']}",
                    "Values": ["owned"],
                },
                {"Name": "status", "Values": ["completed", "pending", "error"]},
                {
                    "Name": "tag:kubernetes.io/created-for/pvc/name",
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
                    "Name": f"tag:kubernetes.io/cluster/{args['old_cluster_name']}",
                    "Values": ["owned"],
                },
                {"Name": "status", "Values": ["completed", "pending", "error"]}
            ],
            OwnerIds=["self"],
        )

    snapshots = response["Snapshots"]
    snapshot_tags = {}

    if len(snapshots) == 0:
        print("No snapshots found")
        return

    for snap in snapshots:

        old_tags = snap["Tags"]
        snap_claim_name = None

        # tags = [{'Key': 'string','Value': 'string'},]
        new_tags = []

        do_not_do = False

        for tag in old_tags:
            if tag["Key"] in [
                "server-stop-time",
                "snapshot-delete-time",
                "ebs.csi.aws.com/cluster",
                "volume-delete-time",
                "server-start-time",
            ]:
                new_tags.append(tag)

            elif tag["Key"] == "kubernetes.io/created-for/pvc/name":
                snap_claim_name = tag["Value"]
                new_tags.append(tag)

                if tag["Value"] == 'hub-db-dir':
                    do_not_do = True

            elif tag["Key"] == "Name":
                new_tags.append({"Key": "Name", "Value": f"migrated-{tag['Value']}"})

            elif tag["Key"] == "osl-billing":
                new_tags.append(
                    {"Key": "osl-billing", "Value": args["new_billing_value"]}
                )

            elif tag["Key"] == f"kubernetes.io/cluster/{args['old_cluster_name']}":
                new_tags.append(
                    {
                        "Key": f"kubernetes.io/cluster/{args['new_cluster_name']}",
                        "Value": "owned",
                    }
                )

            elif tag["Key"] == "KubernetesCluster":
                new_tags.append(
                    {"Key": "KubernetesCluster", "Value": args["new_cluster_name"]}
                )

        if do_not_do:
            continue

        new_tags.append({"Key": f"from-{args['old_cluster_name']}", "Value": "true"})

        # Is there already a snapshot for the particular claim that has the "newer" tags? Then skip.
        claim_snapshots = ec2.describe_snapshots(
            Filters=[
                {
                    "Name": "tag:kubernetes.io/created-for/pvc/name",
                    "Values": [f"{snap_claim_name}"],
                },
                {
                    "Name": f"tag:from-{args['old_cluster_name']}",
                    "Values": ["true"],
                },
            ],
            OwnerIds=["self"],
        )
        if claim_snapshots["Snapshots"]:
            print(f"claim snapshots: {claim_snapshots}")
            print(
                f"Snapshot {claim_snapshots['Snapshots'][0]['SnapshotId']} for claim {snap_claim_name} in volume {snap['SnapshotId']} already exists. Not creating new snapshot.\n"
            )
            continue

        print(f"Copying snapshot: {snap['SnapshotId']}\n")

        try:
            response = ec2.copy_snapshot(
                SourceRegion=args["old_region_name"],
                SourceSnapshotId=snap["SnapshotId"],
                TagSpecifications=[
                    {"ResourceType": "snapshot", "Tags": new_tags},
                ],
                DryRun=False,
            )

        except ec2.exceptions.ClientError as e:
            print(e)
            if not e.response["Error"]["Code"] == "DryRunOperation":
                print("Too many pending snapshots. Wait for 1 minute and continue.")
                time.sleep(60)

        if not response:
            # We are in Dry-Run mode
            snapshot_id = "snap-0c84f7600f7e21fb3"
        else:
            if "Snapshots" in response.keys():
                snapshot_id = response["Snapshots"][0]["SnapshotId"]
            else:
                snapshot_id = response["SnapshotId"]

        snapshot_id = response["SnapshotId"]

        # Modify permissions of snapshot and ADD NEW ACCOUNT NUMBER, as needed
        if args["new_account_id"]:
            print(f"Modifiying permissions for snapshot {snapshot_id}")
            try:
                response = ec2.modify_snapshot_attribute(
                    Attribute="createVolumePermission",
                    OperationType="add",
                    SnapshotId=snapshot_id,
                    UserIds=[
                        args["new_account_id"],
                    ],
                    DryRun=False,
                )
            except ec2.exceptions.ClientError as e:
                print(e)
            except Exception as e:
                print(e)

        snapshot_tags[snapshot_id] = new_tags

    old_json = {}
    try:
        with open("new_tags.json", 'r') as f:
            old_json = json.load(f)
    except FileNotFoundError as e:
        print(f"{e}")

    with open("new_tags.json", 'w') as f:
        json.dump(snapshot_tags | old_json, f)
        f.write("\n")


if __name__ == "__main__":
    # If getting all user claims and not just one specific, set "specific_user_claim" to None.
    args = {
        "old_cluster_name": "smce-test-cluster",
        "new_cluster_name": "smce-prod-cluster",
        "new_billing_value": "smce-prod",
        "new_account_id": "381492216607",
        "old_region_name": "us-west-2",
        "specific_user_claim": "claim-emlundell",
    }

    main(args)
