#!/usr/bin/env python3

######
#
# Clone snapshots from same account.
# TODO Update comment
# The script "take_snapshots_of_volumes_for_another_account" is used to take snapshots of volumes. However, this does not capture snapshots without accompying volumes that still need to be migrated.
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
                {"Name": "status", "Values": ["completed", "pending", "error"]},
                {
                    "Name": f"tag:kubernetes.io/created-for/pvc/name",
                    "Values": [f"args['specific_user_claim']"],
                },
            ],
            OwnerIds=["self"],
        )

    snapshots = response["Snapshots"]

    if len(snapshots) == 0:
        print("No snapshots found")

    if len(snapshots) > 0:
        for snap in snapshots:
            # Filter out any tags with "from-{cluster}" since they are assumed to be created by volumes.
            if f"from-{args['old_cluster_name']}" in snap["Tags"]:
                continue

            print(f"Cloning snapshot: {snap}]\n\n")

            old_tags = snap["Tags"]
            # tags = [{'Key': 'string','Value': 'string'},]
            new_tags = []

            for tag in old_tags:
                if tag["Key"] in [
                    "server-stop-time",
                    "snapshot-delete-time",
                    "ebs.csi.aws.com/cluster",
                    "kubernetes.io/created-for/pvc/name",
                    "volume-delete-time",
                    "server-start-time",
                ]:
                    new_tags.append(tag)

                elif tag["Key"] == "Name":
                    new_tags.append(
                        {"Key": "Name", "Value": f"migrated-{tag['Value']}"}
                    )

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

                elif tag["Key"] == f"KubernetesCluster":
                    new_tags.append(
                        {"Key": f"KubernetesCluster", "Value": args["new_cluster_name"]}
                    )

            new_tags.append(
                {"Key": f"from-{args['old_cluster_name']}", "Value": "true"}
            )

            print(old_tags)
            print(new_tags)

            try:
                response = ec2.copy_snapshot(
                    SourceRegion=args["old_region_name"],
                    SourceSnapshotId=snap["SnapshotId"],
                    TagSpecifications=[
                        {"ResourceType": "snapshot", "Tags": new_tags},
                    ],
                    DryRun=True,
                )

            except ec2.exceptions.ClientError as e:
                print(e)
                if not e.response["Error"]["Code"] == "DryRunOperation":
                    time.sleep(60)

            if (
                "Error" in response.keys()
                and "Code" in response["Error"].keys()
                and response["Error"]["Code"] == "DryRunOperation"
            ):
                snapshot_id = snap["SnapshotId"]
            else:
                assert(len(response["Snapshots"]) == 1)
                snapshot_id = response["Snapshots"][0]["SnapshotId"]

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
                        DryRun=True,
                    )
                except ec2.exceptions.ClientError as e:
                    print(e)


if __name__ == "__main__":
    args = {
        "old_cluster_name": "smce-test-cluster",
        "new_cluster_name": "smce-prod-cluster",
        "new_billing_value": "smce-prod",
        "new_account_id": "381492216607",
        "old_region_name": "us-west-2",
        "specific_user_claim": "claim-emlundell",
    }

    main(args)
