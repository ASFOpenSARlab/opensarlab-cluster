#!/usr/bin/env python3


def delete_volumes():
    try:
        import os
        import datetime
        import yaml
        import boto3
        from kubernetes import client as k8s_client
        from kubernetes import config as k8s_config
        from kubernetes.client.rest import ApiException

        print("Checking for expired volumes...")

        with open("/srv/etc/meta.yaml", 'r') as f:
            data = f.read()

        meta = yaml.safe_load(data)

        namespace = meta['namespace']
        days_inactive_till_termination = meta['days_inactive_till_termination']
        cluster_name = meta['cluster_name']
        region_name = meta['region_name']
        aws_secret_access_key = meta['aws_secret_access_key']
        aws_access_key_id = meta['aws_access_key_id']

        os.environ['KUBERNETES_SERVICE_PORT'] = meta['kubernetes_service_port']
        os.environ['KUBERNETES_SERVICE_HOST'] = meta['kubernetes_service_host']

        k8s_config.load_incluster_config()
        api = k8s_client.CoreV1Api()

        # Cycle through all the volumes in a cluster
        session = boto3.Session(aws_secret_access_key=aws_secret_access_key, aws_access_key_id=aws_access_key_id, region_name=region_name)
        ec2 = session.client('ec2')

        print(f"Searching for volumes in cluster '{cluster_name}' to delete...")

        vols = ec2.describe_volumes(
            Filters=[
                {
                    'Name': 'tag:kubernetes.io/cluster/{0}'.format(cluster_name),
                    'Values': ['owned']
                },
                {
                    'Name': 'tag:kubernetes.io/created-for/pvc/name',
                    'Values': ['*']
                },
                {
                    'Name': 'status',
                    'Values': ['available']
                }
            ]
        )

        vols = vols['Volumes']

        print(f"Number of vols: {len(vols)}")
        if len(vols) == 0:
            vols = []

        for vol in vols:

            vol_id = vol['VolumeId']
            print(f"Checking volume {vol_id}...")

            # Do not delete the Hub DB!!
            if [v['Value'] for v in vol['Tags'] if v['Value'] == 'hub-db-dir']:
                print("Volume 'hub-db-dir' found. Skipping....")
                continue

            # Do not delete if tagged as such
            if [v['Value'] for v in vol['Tags'] if v['Key'] == 'do-not-delete']:
                print(f"Volume '{vol_id}' tagged 'do-not-delete'. Skipping....")
                continue

            # Get last stopped tags
            last_stopped = [v['Value'] for v in vol['Tags'] if v['Key'] == 'jupyter-volume-stopping-time']
            if len(last_stopped) != 1:
                print(f"Volume '{vol_id}' is tagged with last_stopped '{last_stopped}' and is not useable. Skipping...")
                continue

            last_stopped = last_stopped[0]

            pvc_name = [v['Value'] for v in vol['Tags'] if v['Key'] == 'kubernetes.io/created-for/pvc/name'][0]

            # Get snapshot
            snap = ec2.describe_snapshots(
                Filters=[
                    {
                        'Name': 'tag:kubernetes.io/created-for/pvc/name',
                        'Values': ['{0}'.format(pvc_name)]
                    },
                    {
                        'Name': 'tag:kubernetes.io/cluster/{0}'.format(cluster_name),
                        'Values': ['owned']
                    },
                    {
                        'Name': 'status',
                        'Values': ['completed']
                    }
                ],
                OwnerIds=['self']
            )
            snap = snap['Snapshots']

            has_snapshot = False
            if len(snap) == 0:
                print("WARNING: No snapshots have been found.")
            else:
                cutoff_days = 2
                for s in snap:
                    since_snapshot = datetime.datetime.now() - datetime.datetime.strptime(s['StartTime'], '%Y-%m-%d %H:%M:%S.%f')
                    time_diff = since_snapshot - datetime.timedelta(days=cutoff_days)
                    if time_diff > 0:
                        print(f"Warning: Snapshot {s['SnapshotId']} is {since_snapshot} old.")
                    else:
                        has_snapshot = True

                if has_snapshot is False:
                    print(f"No snapshots found newer than {cutoff_days} old. Will not delete volume '{vol_id}'.")

            # Get time difference between now and when the volume was last used.
            time_diff = datetime.datetime.now() - datetime.datetime.strptime(last_stopped, '%Y-%m-%d %H:%M:%S.%f') - datetime.timedelta(days=days_inactive_till_termination)
            print("time diff: ", time_diff)
            do_deactivate = time_diff.total_seconds() > 0
            is_available = vol['State'] == 'available'

            print(f"do_deactivate: {do_deactivate}, has_snapshot: {has_snapshot}, is_available: {is_available}")
            if is_available and has_snapshot and do_deactivate:
                # Delete PVC
                print(f"Delete pvc '{pvc_name}'")
                try:
                    api.delete_namespaced_persistent_volume_claim(body=k8s_client.V1DeleteOptions(), name=pvc_name, namespace=namespace, dry_run=True)
                except ApiException as e:
                    print("Did not delete volume...")
                    print(e)

    except Exception as e:
        print(e)


if __name__ == "__main__":
    delete_volumes()
