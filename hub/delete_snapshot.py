#!/usr/bin/env python3


def delete_snapshot():
    try:
        import yaml
        import boto3

        print("Checking for expired volumes...")

        with open("/srv/etc/meta.yaml", 'r') as f:
            data = f.read()

        meta = yaml.safe_load(data)

        cluster_name = meta['cluster_name']
        region_name = meta['region_name']
        aws_secret_access_key = meta['aws_secret_access_key']
        aws_access_key_id = meta['aws_access_key_id']

        # Cycle through all the volumes in a cluster
        session = boto3.Session(aws_secret_access_key=aws_secret_access_key, aws_access_key_id=aws_access_key_id, region_name=region_name)
        ec2 = session.client('ec2')

        # Get snapshot
        snap = ec2.describe_snapshots(
            Filters=[
                {
                    'Name': 'tag:kubernetes.io/cluster/{0}'.format(cluster_name),
                    'Values': ['owned']
                },
                {
                    'Name': 'status',
                    'Values': ['completed']
                },
                {
                    'Name': 'tag:kubernetes.io/created-for/pvc/name',
                    'Values': ['*']
                }
            ],
            OwnerIds=['self']
        )
        snap = snap['Snapshots']

        if len(snap) > 0:
            hash_table = {}
            for s in snap:
                # Create a hash table with the pvc name (which is presumed to be unique) as the key. Then we can sort out the older snapshots.
                pvc = [v['Value'] for v in s['Tags'] if v['Key'] == 'kubernetes.io/created-for/pvc/name'][0]
                h = str(abs(hash(pvc)))
                try:
                    a = hash_table[h]
                    a.append(s)
                    hash_table[h] = a
                except Exception:
                    hash_table[h] = [s]

            for i in hash_table:
                try:
                    snaps = hash_table[i]
                    snaps = sorted(snaps, key=lambda s: s['StartTime'], reverse=True)
                    if len(snaps) > 1:
                        # Always keep the newest snapshot of the group
                        snaps = snaps[1:]
                        for s in snaps:
                            if not [v['Value'] for v in s['Tags'] if v['Key'] == 'do-not-delete']:
                                print(f"**** Deleting {s['SnapshotId']}")
                                ec2.delete_snapshot(SnapshotId=s['SnapshotId'], DryRun=False)
                except Exception as e:
                    print("Something went wrong with deleting the snapshots...")
                    print(e)

    except Exception as e:
        print(e)


if __name__ == "__main__":
    delete_snapshot()
