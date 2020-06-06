#!/usr/bin/env python3

def send_email(send_to, header, body, session):

    sns = session.client('sns')

def send_email_if_expired_and_maybe_delete(days_inactive_till_trigger, snap, session):

    import datetime

    cognito = session.client('cognito')
    ec2 = session.client('ec2')

    today = datetime.datetime.now()

    volume_stopped_tag_date = ''
    username = ''
    days_inactive = ''
    send_to = ''

    send_email_if = days_inactive_till_trigger[0:-1]
    send_email_and_deactivate_if = days_inactive_till_trigger[-1]

    for d in send_email_if:
        if days_inactive == d:
            email_header = "OpenSARlab account notifcation"
            email_body = "The OpenSARlab account for {username} will be deactivated in {num_days} days. Any user data will deleted permanently. To stop this action, please sign back into your OpenSARlab account."
            send_email(send_to, email_header, email_body, session)

    if days_inactive >= send_email_and_deactivate_if:

        # Deaactivate account

        # Delete remaining snapshot

        email_header = "OpenSARlab account notifcation"
        email_body = "The OpenSARlab account for {username} has been deactivated. All user data has been deleted permanently."
        send_email(send_to, (email_header, email_body, session)


def delete_snapshot():
    try:
        import yaml
        import boto3

        print("Checking for expired volumes...")

        with open("/etc/jupyterhub/custom/meta.yaml", 'r') as f:
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
                        extra_snaps = snaps[1:]
                        for s in extra_snaps:
                            if not [v['Value'] for v in s['Tags'] if v['Key'] == 'do-not-delete']:
                                print(f"**** Deleting {s['SnapshotId']}")
                                ec2.delete_snapshot(SnapshotId=s['SnapshotId'], DryRun=False)
                    
                    snap = snaps[0]

                    # Send email deletion warning and/or delete as needed
                    if not [v['Value'] for v in snap['Tags'] if v['Key'] == 'do-not-delete']:
                        send_email_if_expired_and_maybe_delete([30,44,46], snap, session)

                except Exception as e:
                    print("Something went wrong with snapshot handling...")
                    print(e)

    except Exception as e:
        print(e)


if __name__ == "__main__":
    delete_snapshot()
