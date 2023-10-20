#!/usr/bin/env python3

import boto3
import datetime

import logging
logging.basicConfig(format='%(asctime)s %(levelname)s (%(lineno)d) - %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)

import z2jh

def _get_delta_time(days: int) -> datetime:
    """
        Get datetime now in UTC. 
        Add number of `days` until event.
        We don't need second and millisecond resolution so make those 0.
    """
    the_future_in_utc = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    return the_future_in_utc.replace(second=0, microsecond=0)

def server_stopping_tags(spawner):
    pvc_name = spawner.pvc_name
    cluster_name = z2jh.get_config('custom.CLUSTER_NAME')
    region_name = z2jh.get_config('custom.AWS_REGION')

    days_till_volume_deletion = z2jh.get_config('custom.DAYS_TILL_VOLUME_DELETION')
    days_till_snapshot_deletion = z2jh.get_config('custom.DAYS_TILL_SNAPSHOT_DELETION')

    session = boto3.Session(region_name=region_name)
    ec2 = session.client('ec2')

    log.info(f"Updating stopping tags to '{pvc_name}' in cluster '{cluster_name}'...")

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
                    'Key': 'server-stop-time',
                    'Value': '{0}'.format(_get_delta_time(days=0))
                },
                {
                    'Key': 'volume-delete-time',
                    'Value': '{0}'.format(_get_delta_time(days=days_till_volume_deletion))
                },
                {
                    'Key': 'snapshot-delete-time',
                    'Value': '{0}'.format(_get_delta_time(days=days_till_snapshot_deletion))
                },
            ]
        )

# After stopping the notebook server, tag the volume with the current "stopping" time. This will help determine which volumes are active.
def my_post_hook(spawner):
    try:
        server_stopping_tags(spawner)

    except Exception as e:
        log.error("Something went wrong with the volume stopping tag post hook...")
        log.error(e)
        raise

c.Spawner.post_stop_hook = my_post_hook
