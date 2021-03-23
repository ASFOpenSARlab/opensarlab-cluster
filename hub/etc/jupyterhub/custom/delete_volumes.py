#!/usr/bin/env python3
def _get_tags(vol, key):
    return [v['Value'] for v in vol['Tags'] if v['Key'] == key]

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

        with open("/etc/jupyterhub/custom/meta.yaml", 'r') as f:
            data = f.read()

        meta = yaml.safe_load(data)

        namespace = meta['namespace']
        days_inactive_till_termination = meta['days_vol_inactive_till_termination']
        cluster_name = meta['cluster_name']
        region_name = meta['region_name']

        os.environ['KUBERNETES_SERVICE_PORT'] = meta['kubernetes_service_port']
        os.environ['KUBERNETES_SERVICE_HOST'] = meta['kubernetes_service_host']

        k8s_config.load_incluster_config()
        api = k8s_client.CoreV1Api()

        # Cycle through all the volumes in a cluster
        session = boto3.Session(region_name=region_name)
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
            if _get_tags(vol, 'hub-db-dir'):
                print("Volume 'hub-db-dir' found. Skipping....")
                continue

            # Do not delete if tagged as such
            if _get_tags(vol, 'do-not-delete'):
                print(f"Volume '{vol_id}' tagged 'do-not-delete'. Skipping....")
                continue

            # Get last stopped tags
            last_stopped = _get_tags(vol, 'jupyter-volume-stopping-time')
            if len(last_stopped) != 1:
                print(f"Volume '{vol_id}' is tagged with last_stopped '{last_stopped}' and is not useable. Skipping...")
                continue

            last_stopped = last_stopped[0]

            pvc_name = _get_tags(vol, 'kubernetes.io/created-for/pvc/name')[0]

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

            has_valid_snapshot = False
            if len(snap) == 0:
                print("WARNING: No snapshots have been found.")
            else:
                # If the snapshot lifecycle policy fails, daily snapshots will stop and snapshots will slowly age out and get out of sync with the volumes.
                # If someone later stops their volumes for more than the delete threshold, then that volume will be deleted.
                # Since the snapshot is out of sync, restoring from the snapshot will give bad data.
                # To avoid this, don't delete volumes when all the corresponding snapshots are too old.

                days_till_too_old = 2

                snapshots_too_old = [True for s in snap if s['StartTime'] < datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_till_too_old)]
                if len(snapshots_too_old) == len(snap):
                    print(f"No snapshots found newer than {days_till_too_old} days old. Will not delete volume '{vol_id}'.")
                else:
                    has_valid_snapshot = True

            # Get time difference between now and when the volume was last used.
            time_diff = datetime.datetime.strptime(last_stopped, '%Y-%m-%d %H:%M:%S.%f') + datetime.timedelta(days=days_inactive_till_termination) - datetime.datetime.now()
            print("Days till volume is too old: ", time_diff)
            do_deactivate = time_diff.total_seconds() < 0
            is_available = vol['State'] == 'available'

            print(f"do_deactivate: {do_deactivate}, has_valid_snapshots: {has_valid_snapshot}, is_available: {is_available}")
            if is_available and has_valid_snapshot and do_deactivate:
                # Delete PVC
                print(f"Delete pvc '{pvc_name}'")
                try:
                    api.delete_namespaced_persistent_volume_claim(body=k8s_client.V1DeleteOptions(), name=pvc_name, namespace=namespace)
                except ApiException as e:
                    print("Did not delete volume...")
                    print(e)

    except Exception as e:
        print(e)


if __name__ == "__main__":
    delete_volumes()
