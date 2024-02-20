#!/usr/bin/env python3

######
#
# Take snapshots of user volumes and make sure they have the right tags (for the new account/region).
# Meant to be run in cloudshell of the particular region/account where the proper environment varibles are set.
#
######

import boto3

import time


def main(args):
    # Initialize Boto3
    session = boto3.Session()
    ec2 = session.client("ec2")

    if args["specific_user_claim"]:
        # Get specfic volume of a particular user (if it exists)
        volumes = ec2.describe_volumes(
            Filters=[
                {
                    "Name": f"tag:kubernetes.io/cluster/{args['old_cluster_name']}",
                    "Values": ["owned"],
                },
                {
                    "Name": f"tag:kubernetes.io/created-for/pvc/name",
                    "Values": [f"{args['specific_user_claim']}"],
                },
            ],
        )

    else:
        # Get list of volumes belonging to particular cluster
        volumes = ec2.describe_volumes(
            Filters=[
                {
                    "Name": f"tag:kubernetes.io/cluster/{args['old_cluster_name']}",
                    "Values": ["owned"],
                },
            ]
        )

    volumes = volumes["Volumes"]

    if len(volumes) == 0:
        print("No volumes found")

    if len(volumes) > 0:
        # Take snapshots of each volume. Make sure the tags are copied over.
        for vol in volumes:
            print(f"Converting tags for volume: {vol}]\n\n")

            old_tags = vol["Tags"]
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

            print(f"Creating snapshot from volume: {vol['VolumeId']}\n")

            response = ec2.create_snapshot(
                VolumeId=vol["VolumeId"],
                TagSpecifications=[
                    {"ResourceType": "snapshot", "Tags": new_tags},
                ],
                DryRun=False,
            )

            snapshot_id = response["SnapshotId"]

            # Modify permissions of snapshot and ADD NEW ACCOUNT NUMBER, as needed
            if args["new_account_id"]:
                print(
                    f"Modifiying permissions for snapshot {snapshot_id} from volume {vol['VolumeId']}"
                )
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
                except ec2.exceptions.ClientError:
                    print("Too many pending snapshots. Wait for 1 minute and continue.")
                    time.sleep(60)
                except ec2.meta.client.exceptions.DryRunOperation:
                    print("Dry Run Operation has all necessary permissions")


if __name__ == "__main__":
    args = {
        "old_cluster_name": "smce-test-cluster",
        "new_cluster_name": "smce-prod-cluster",
        "new_billing_value": "smce-prod",
        "new_account_id": "381492216607",
        "specific_user_claim": "claim-emlundell",
    }

    main(args)
