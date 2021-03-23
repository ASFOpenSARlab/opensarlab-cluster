#!/usr/bin/env python3

import os
import re

import yaml
import boto3
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException


def volume_from_snapshot(meta):
    try:
        pwd = os.path.dirname(os.path.abspath(__file__))

        k8s_config.load_incluster_config()
        api = k8s_client.CoreV1Api()

        username = meta['username']
        pvc_name = meta['pvc_name']
        namespace = meta['namespace']
        cluster_name = meta['cluster_name']
        az_name = meta['az_name']
        vol_size = meta['vol_size']
        spawn_pvc = meta['spawn_pvc']
        region_name = az_name[:-1]

        print(f"Spawner gives storage as {vol_size}")

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
                                {'Key': 'RestoredFromSnapshot', 'Value': 'True'},
                                {'Key': 'osl-stackname', 'Value': cluster_name}
                            ]
                        },
                    ]
                )
                vol_id = vol['VolumeId']
                print(f"Volume {vol_id} created.")

                this_val = [v['Value'] for v in snapshot['Tags'] if v['Key'] == 'jupyter-volume-stopping-time']
                if this_val:
                    ec2.create_tags(DryRun=False, Resources=[vol_id], Tags=[
                            {
                                'Key': 'jupyter-volume-stopping-time',
                                'Value': str(this_val[0])
                            },])

                # If do-not-delete tag was present in snapshot, add to volume tags
                if [v['Value'] for v in snapshot['Tags'] if v['Key'] == 'do-not-delete']:
                    ec2.create_tags(DryRun=False, Resources=[vol_id], Tags=[
                            {
                                'Key': 'do-not-delete',
                                'Value': 'True'
                            },])

                annotations = spawn_pvc.metadata.annotations
                labels = spawn_pvc.metadata.labels

                # Get PVC manifest
                with open(f"{pwd}/pvc.yaml", mode='r') as f:
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
                with open(f"{pwd}/pv.yaml", mode='r') as f:
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
    except Exception as e:
        print(e)
