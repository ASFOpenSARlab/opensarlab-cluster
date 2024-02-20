#!/usr/bin/env python3

import datetime
import boto3
import z2jh

import logging
logging.basicConfig(format='%(asctime)s %(levelname)s (%(lineno)d) - %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)

def get_tag_value(resource, key):
    
    val = [s['Value'] for s in resource['Tags'] if s['Key'] == key]

    if not val:
        val = ['']

    return str(val[0])

def use_existing_volume_or_snapshot(spawner):
    """
    # Before mounting the home directory, check to see if a volume exists.
    # If it doesn't, check for any EBS snapshots.
    # If a snapshot exists, create a volume from the snapshot.
    # Otherwise, JupyterHub will do the mounting and other volume handling.
    """

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
    etc_dir = "/usr/local/etc/jupyterhub/jupyterhub_config.d/etc"

    log.info(f"Spawner gives storage as {vol_size}. If restoring from a snapshot, the size may be different.")

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
            log.warning("PVC '{pvc_name}' exists! Therefore a volume should have already been assigned to user '{username}'.".format(pvc_name=pvc_name, username=username))
            has_pvc = True

    if not has_pvc:
        log.warning("PVC '{pvc_name}' does not exist. Therefore a volume will have to be created for user '{username}'.".format(pvc_name=pvc_name, username=username))

        # Does the user have any volumes?
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

        volumes = vol['Volumes']
        if len(volumes) > 1:
            volumes = sorted(volumes, key=lambda s: s['CreateTime'], reverse=True)
            log.warning(f"\nWARNING ***** More than one volume found for pvc name: {pvc_name}. Claiming the latest one: \n{volumes[0]}.")
        elif len(volumes) == 0:
            log.info(f"No volumes found that matched pvc name '{pvc_name}'")
            volumes = [None]

        volume = volumes[0]

        log.info(f"No PVC but Volume for {pvc_name}: {volume}")

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
            log.warning(f"\nWARNING ***** More than one snapshot found for pvc: {pvc_name}. Claiming the latest one: \n{snap[0]}.")
        elif len(snap) == 0:
            log.info(f"No snapshot found that matched pvc '{pvc_name}'")
            snap = [None]

        snapshot = snap[0]

        log.info(f"No PVC but Snapshot for {pvc_name}: {snapshot}")

        # If there is no existing volume or snapshot, we will let JupyterHub create a new volume and PVC
        if not volume and not snapshot:
            log.info(f"No volumes found nor able to restore from snapshot. Allow JupyterHub to create a new volume for {pvc_name}")
            return
        
        CREATE_PVC_FROM_EXISTING_VOLUME = False
        CREATE_PVC_FROM_SNAPSHOT = True

        # If there is an existing volume, do not restore from any possible snapshot
        if CREATE_PVC_FROM_EXISTING_VOLUME and volume:
            log.info(f"Volume found for {pvc_name}. Will create matching PVC. Ignoring any snapshots.")

        # If there is no existing volume but there is a snapshot, restore volume from the snapshot 
        elif CREATE_PVC_FROM_SNAPSHOT and not volume and snapshot:

            # Guarantee that the volume never shrinks if the spawner's volume is smaller than the snapshot
            if snapshot['VolumeSize'] > vol_size:
                vol_size = snapshot['VolumeSize']

            log.info("Creating volume from snapshot...")
            volume = ec2.create_volume(
                AvailabilityZone=az_name,
                Encrypted=False,
                Size=vol_size,
                SnapshotId=snapshot['SnapshotId'],
                VolumeType='gp3',
                DryRun=False,
                TagSpecifications=[
                    {
                        'ResourceType': 'volume',
                        'Tags': [
                            {'Key': 'Name', 'Value': '{username}-{cluster_name}'.format(cluster_name=cluster_name, username=username)},
                            {'Key': 'kubernetes.io/cluster/{cluster_name}'.format(cluster_name=cluster_name), 'Value': 'owned'},
                            {'Key': 'kubernetes.io/created-for/pvc/namespace', 'Value': namespace},
                            {'Key': 'kubernetes.io/created-for/pvc/name', 'Value': pvc_name},
                            {'Key': 'RestoredFromSnapshot', 'Value': snapshot['SnapshotId']}
                        ]
                    },
                ]
            )
            log.info(f"Volume {volume['VolumeId']} created.")

            this_val = get_tag_value(snapshot, 'jupyter-volume-stopping-time')
            if this_val:
                ec2.create_tags(DryRun=False, Resources=[volume['VolumeId']], Tags=[
                        {
                            'Key': 'jupyter-volume-stopping-time',
                            'Value': this_val
                        },])

            # If do-not-delete tag was present in snapshot, add to volume tags
            if get_tag_value(snapshot, 'do-not-delete'):
                ec2.create_tags(DryRun=False, Resources=[volume['VolumeId']], Tags=[
                    {
                        'Key': 'do-not-delete',
                        'Value': 'True'
                    },])

            # If the billing tag is present in the snapshot, add to volume tags
            # If the tag doesn't exist in the snapshot, the default is `cost_tag_value`
            this_val = get_tag_value(snapshot, cost_tag_key)
            if not this_val:
                this_val = cost_tag_value
            ec2.create_tags(DryRun=False, Resources=[volume['VolumeId']], Tags=[
                {
                    'Key': cost_tag_key,
                    'Value': this_val
                },])

        annotations = spawn_pvc.metadata.annotations

        # Explicit annote the provisioner. The CSI plugin appears to not do this properly.
        # May not be needed
        #annotations.update({"pv.kubernetes.io/provisioned-by": "ebs.csi.aws.com"})

        labels = spawn_pvc.metadata.labels

        # Get PVC manifest
        with open(f"{etc_dir}/pvc.yaml", mode='r') as f:
            pvc_yaml = f.read().format(
                annotations=annotations,
                cluster_name=cluster_name,
                labels=labels,
                name=pvc_name,
                namespace=namespace,
                vol_size=volume['Size'],
                vol_id=volume['VolumeId']
            )

        pvc_manifest = yaml.safe_load(pvc_yaml)

        # Get PV manifest
        with open(f"{etc_dir}/pv.yaml", mode='r') as f:
            pv_yaml = f.read()

        annotations = pvc_manifest['metadata']['annotations']

        pv_yaml = pv_yaml.format(
                annotations=annotations,
                cluster_name=cluster_name,
                region_name=region_name,
                az_name=az_name,
                pvc_name=pvc_name,
                namespace=namespace,
                vol_id=volume['VolumeId'],
                storage=pvc_manifest['spec']['resources']['requests']['storage']
            )

        pv_manifest = yaml.safe_load(pv_yaml)

        # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CoreV1Api.md#create_persistent_volume
        log.info("Creating persistent volume...")
        try:
            api.create_persistent_volume(body=pv_manifest)
        except ApiException as e:
            if e.status == 409:
                log.info(f"PV {volume['VolumeId']} already exists, so did not create new pvc.")
            else:
                raise

        # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CoreV1Api.md#create_namespaced_persistent_volume_claim
        log.info("Creating persistent volume claim...")
        try:
            api.create_namespaced_persistent_volume_claim(body=pvc_manifest, namespace=namespace)
        except ApiException as e:
            if e.status == 409:
                log.info(f"PVC {pvc_name} already exists, so did not create new pvc.")
            else:
                raise

def server_starting_tag(spawner):

    pvc_name = spawner.pvc_name
    cluster_name = z2jh.get_config('custom.CLUSTER_NAME')
    az_name =  z2jh.get_config('custom.AZ_NAME')
    region_name = az_name[:-1]

    session = boto3.Session(region_name=region_name)
    ec2 = session.client('ec2')

    log.info(f"Updating starting tags to '{pvc_name}' in cluster '{cluster_name}'...")

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
                    'Key': 'server-start-time',
                    'Value': '{0}'.format(datetime.datetime.now(datetime.timezone.utc).replace(second=0, microsecond=0))
                },
            ]
        )

def my_pre_hook(spawner):
    try:
        use_existing_volume_or_snapshot(spawner)
        server_starting_tag(spawner)

    except Exception as e:
        log.error(e)
        raise

c.Spawner.pre_spawn_hook = my_pre_hook
