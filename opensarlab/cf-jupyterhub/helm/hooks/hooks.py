#!/usr/bin/env python3

def get_tag_value(resource, key):
    
    val = [s['Value'] for s in resource['Tags'] if s['Key'] == key]

    if not val:
        val = ['']

    return str(val[0])

def volume_from_snapshot(spawner):

    import re

    import boto3
    import yaml
    from kubernetes import client as k8s_client
    from kubernetes import config as k8s_config
    from kubernetes.client.rest import ApiException

    import z2jh

    k8s_config.load_incluster_config()
    api = k8s_client.CoreV1Api()

    username = spawner.user.name
    pvc_name = spawner.pvc_name
    namespace = 'jupyter'
    cluster_name = z2jh.get_config('custom.CLUSTER_NAME')
    cost_tag_key = z2jh.get_config('custom.COST_TAG_KEY')
    cost_tag_value = z2jh.get_config('custom.COST_TAG_VALUE')
    az_name = z2jh.get_config('custom.AZ_NAME')
    vol_size = spawner.storage_capacity
    spawn_pvc = spawner.get_pvc_manifest()
    region_name = az_name[:-1]

    print(f"Spawner gives storage as {vol_size}. If restoring from a snapshot, the size may be different.")

    alpha = " ".join(re.findall("[a-zA-Z]+", vol_size)).lower()
    number = int(" ".join(re.findall("[0-9]+", vol_size)))

    possible_units = {
        "ei": 2**60,
        "pi": 2**50,
        "ti": 2**40,
        "gi": 2**30,
        "mi": 2**20,
        "ki": 2**10,
        "e": 10**18,
        "p": 10**15,
        "t": 10**12,
        "g": 10**9,
        "m": 10**6,
        "k": 10**3,
        "": 1
    }

    vol_size = number * possible_units[alpha]

    # Volume needs to be in GiB (an int without the label)
    vol_size = int(vol_size * 2**-30)
    if vol_size < 0:
        vol_size = 1

    session = boto3.Session(region_name=region_name)
    ec2 = session.client('ec2')

    pvcs = api.list_namespaced_persistent_volume_claim(namespace=namespace, watch=False)

    has_pvc = False
    for items in pvcs.items:
        if items.metadata.name == pvc_name:
            print("PVC '{pvc_name}' exists! Therefore a volume should have already been assigned to user '{username}'.".format(pvc_name=pvc_name, username=username))
            has_pvc = True

    if not has_pvc:
        print("PVC '{pvc_name}' does not exist. Therefore a volume will have to be created for user '{username}'.".format(pvc_name=pvc_name, username=username))

        # Does the user have any snapshots?
        snap = ec2.describe_snapshots(
            Filters=[
                {
                    'Name': 'tag:kubernetes.io/created-for/pvc/name',
                    'Values': [pvc_name]
                },
                {
                    'Name': 'tag:kubernetes.io/cluster/{cluster_name}'.format(cluster_name=cluster_name),
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

        if len(snap) > 1:
            snap = sorted(snap, key=lambda s: s['StartTime'], reverse=True)
            print(f"\nWARNING ***** More than one snapshot found for pvc: {pvc_name}. Claiming the latest one: \n{snap[0]}.")
        elif len(snap) == 0:
            print(f"No snapshot found that matched pvc '{pvc_name}'")
            snap = [None]

        snapshot = snap[0]

        if snapshot:
            # Guarantee that the volume never shrinks if the spawner's volume is smaller than the snapshot
            if snapshot['VolumeSize'] > vol_size:
                vol_size = snapshot['VolumeSize']

            print("Creating volume from snapshot...")
            vol = ec2.create_volume(
                AvailabilityZone=az_name,
                Encrypted=False,
                Size=vol_size,
                SnapshotId=snapshot['SnapshotId'],
                VolumeType='gp2',
                DryRun=False,
                TagSpecifications=[
                    {
                        'ResourceType': 'volume',
                        'Tags': [
                            {'Key': 'Name', 'Value': '{username}-{cluster_name}'.format(cluster_name=cluster_name, username=username)},
                            {'Key': 'kubernetes.io/cluster/{cluster_name}'.format(cluster_name=cluster_name), 'Value': 'owned'},
                            {'Key': 'kubernetes.io/created-for/pvc/namespace', 'Value': namespace},
                            {'Key': 'kubernetes.io/created-for/pvc/name', 'Value': pvc_name},
                            {'Key': 'RestoredFromSnapshot', 'Value': 'True'}
                        ]
                    },
                ]
            )
            vol_id = vol['VolumeId']
            print(f"Volume {vol_id} created.")

            this_val = get_tag_value(snapshot, 'jupyter-volume-stopping-time')
            if this_val:
                ec2.create_tags(DryRun=False, Resources=[vol_id], Tags=[
                        {
                            'Key': 'jupyter-volume-stopping-time',
                            'Value': this_val
                        },])

            # If do-not-delete tag was present in snapshot, add to volume tags
            if get_tag_value(snapshot, 'do-not-delete'):
                ec2.create_tags(DryRun=False, Resources=[vol_id], Tags=[
                    {
                        'Key': 'do-not-delete',
                        'Value': 'True'
                    },])

            # If the billing tag is present in the snapshot, add to volume tags
            # If the tag doesn't exist in the snapshot, the default is `cost_tag_value`
            this_val = get_tag_value(snapshot, cost_tag_key)
            if not this_val:
                this_val = cost_tag_value
            ec2.create_tags(DryRun=False, Resources=[vol_id], Tags=[
                {
                    'Key': cost_tag_key,
                    'Value': this_val
                },])

            annotations = spawn_pvc.metadata.annotations
            labels = spawn_pvc.metadata.labels

            # Get PVC manifest
            with open("/home/jovyan/hooks/pvc.yaml", mode='r') as f:
                pvc_yaml = f.read().format(
                    annotations=annotations,
                    cluster_name=cluster_name,
                    labels=labels,
                    name=pvc_name,
                    namespace=namespace,
                    vol_size=vol_size,
                    vol_id=vol_id
                )

            pvc_manifest = yaml.safe_load(pvc_yaml)

            # Get PV manifest
            with open("/home/jovyan/hooks/pv.yaml", mode='r') as f:
                pv_yaml = f.read()

            annotations = pvc_manifest['metadata']['annotations']

            pv_yaml = pv_yaml.format(
                    annotations=annotations,
                    cluster_name=cluster_name,
                    region_name=region_name,
                    az_name=az_name,
                    pvc_name=pvc_name,
                    namespace=namespace,
                    vol_id=vol_id,
                    storage=pvc_manifest['spec']['resources']['requests']['storage']
                )

            pv_manifest = yaml.safe_load(pv_yaml)

            # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CoreV1Api.md#create_persistent_volume
            print("Creating persistent volume...")
            try:
                api.create_persistent_volume(body=pv_manifest)
            except ApiException as e:
                if e.status == 409:
                    print(f"PV {vol_id} already exists, so did not create new pvc.")
                else:
                    raise

            # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CoreV1Api.md#create_namespaced_persistent_volume_claim
            print("Creating persistent volume claim...")
            try:
                api.create_namespaced_persistent_volume_claim(body=pvc_manifest, namespace=namespace)
            except ApiException as e:
                if e.status == 409:
                    print(f"PVC {pvc_name} already exists, so did not create new pvc.")
                else:
                    raise

def organize_custom_templates():

    import pathlib

    pathlib.Path("/opt/conda/lib/python3.9/site-packages/notebook/templates/tree.html").rename("/opt/conda/lib/python3.9/site-packages/notebook/templates/original_tree.html")
    pathlib.Path("/opt/conda/lib/python3.9/site-packages/notebook/templates/new_tree.html").rename("/opt/conda/lib/python3.9/site-packages/notebook/templates/tree.html")

    pathlib.Path("/opt/conda/lib/python3.9/site-packages/notebook/templates/page.html").rename("/opt/conda/lib/python3.9/site-packages/notebook/templates/original_page.html")
    pathlib.Path("/opt/conda/lib/python3.9/site-packages/notebook/templates/new_page.html").rename("/opt/conda/lib/python3.9/site-packages/notebook/templates/page.html")

# Before mounting the home directory, check to see if a volume exists.
# If it doesn't, check for any EBS snapshots.
# If a snapshot exists, create a volume from the snapshot.
# Otherwise, JupyterHub will do the mounting and other volume handling.
def my_pre_hook(spawner):
    try:
        volume_from_snapshot(spawner)

        organize_custom_templates()

    except Exception as e:
        print(e)
        raise

c.Spawner.pre_spawn_hook = my_pre_hook

# *******************************************

def volume_stopping_tag(spawner):
    import datetime

    import boto3

    import z2jh

    pvc_name = spawner.pvc_name
    cluster_name = z2jh.get_config('custom.CLUSTER_NAME')
    az_name =  z2jh.get_config('custom.AZ_NAME')
    region_name = az_name[:-1]

    session = boto3.Session(region_name=region_name)
    ec2 = session.client('ec2')

    print(f"Updating stopping tags to '{pvc_name}' in cluster '{cluster_name}'...")

    vol = ec2.describe_volumes(
        Filters=[
            {
                'Name': 'tag:kubernetes.io/created-for/pvc/name',
                'Values': [pvc_name]
            },
            {
                'Name': 'tag:kubernetes.io/cluster/{0}'.format(cluster_name),
                'Values': ['owned']
            }
        ]
    )

    vol = vol['Volumes']

    if len(vol) > 1:
        raise Exception("\n ***** More than one volume for pvc: {0}".format(pvc_name))

    if len(vol) != 1:
        vol = []
    else:
        vol = vol[0]

    if vol:
        ec2.create_tags(
            DryRun=False,
            Resources=[
                vol['VolumeId']
            ],
            Tags=[
                {
                    'Key': 'jupyter-volume-stopping-time',
                    'Value': '{0}'.format(datetime.datetime.now())
                },
            ]
        )

# After stopping the notebook server, tag the volume with the current "stopping" time. This will help determine which volumes are active.
def my_post_hook(spawner):
    try:
        volume_stopping_tag(spawner)

    except Exception as e:
        print("Something went wrong with the volume stopping tag post hook...")
        print(e)
        raise

c.Spawner.post_stop_hook = my_post_hook
