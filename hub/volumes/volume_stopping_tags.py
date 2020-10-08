#!/usr/bin/env python3

import datetime

import boto3


def volume_stopping_tags(meta):

    pvc_name = meta['pvc_name']
    cluster_name = meta['cluster_name']
    az_name = meta['az_name']
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
