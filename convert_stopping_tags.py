#!/usr/bin/env python3

"""
    convert_stopping_tags.py old_days_since_last_run new_days_since_last_run

    Convert all `jupyter-volume-stopping-time` tags older than `old_days_since_last_run` days to `new_days_since_last_run` days. 
    
    This is permanent.

    This small tool is used to re-timestamp volumes so that their snapshots will go through the snapshot deletion process.

    For instance, if a snapshot was last used between 30 and 40 days ago and you wanted to re-timestamp it so it looked like was last used 10 days ago, 

        convert_stopping_tags.py 30-40 10

    Convert volume tags older than 20 days to a day old.

        convert_stopping_tags.py 20- 1 

"""

import datetime
import argparse  
import math

import boto3 

parser = argparse.ArgumentParser()
parser.add_argument("last_used")
parser.add_argument("new_days_since")
parser.add_argument("--dry-run", action="store_true", dest="dry_run")
parser.add_argument("--list-meta", action="store_true", dest="list_meta")
parser.add_argument("--cluster", default="opensarlab-test")
args = parser.parse_args()

dry_run = args.dry_run

last_used = args.last_used
span = last_used.split('-')
if len(span) == 1:
    last_start = int(span[0])
    last_end = int(span[0])
elif len(span) == 2 and span[1] == '':
    last_start = int(span[0])
    last_end = math.inf 
elif len(span) == 2 and span[1] != '':
    last_start = int(span[0])
    last_end = int(span[1])

session = boto3.session.Session(profile_name='jupyterhub')

ec2 = session.client('ec2')

tag_cluster = f"kubernetes.io/cluster/{args.cluster}"
print(f"Working on cluster {tag_cluster}")

res = ec2.describe_snapshots(
    DryRun=False,
    Filters=[
        {
            'Name': 'tag-key',
            'Values': ['jupyter-volume-stopping-time']
        },
        {
            'Name': f'tag:{tag_cluster}', 
            'Values': ['owned']
        },
    ]
)

#print(res)

sr = []
for r in res['Snapshots']:
    try:
        snap_id = r['SnapshotId']
        snap_stopped = [v['Value'] for v in r['Tags'] if v['Key'] == 'jupyter-volume-stopping-time'][0]
        snap_name = [v['Value'] for v in r['Tags'] if v['Key'] == 'kubernetes.io/created-for/pvc/name'][0]

        d1 = datetime.datetime.strptime(snap_stopped, '%Y-%m-%d %H:%M:%S.%f')
        d2 = datetime.datetime.now()
        days = (d2-d1).days

        if args.list_meta:
            print(f"Resource '{snap_id}' has been expired for {days} days")

        if last_start <= days <= last_end:
            print(f"Append '{snap_id}' for '{snap_name}' since {days} days is between {last_start} and {last_end}")
            sr.append( (snap_name, snap_id) )
        else:
            print(f"Skipping '{snap_id}' for '{snap_name}' with {days} days.")

    except Exception as e:
        print(f"Tag {r} has issues: {e}")

if len(sr) == 0:
    print("There are no resource tags to update...")
    exit

print("*****")
d1 = datetime.datetime.now()
new_timestamp = datetime.datetime.strftime(d1 - datetime.timedelta(days=int(args.new_days_since)), '%Y-%m-%d %H:%M:%S.%f')

print(f"Will change {len(sr)} snapshots")
for snap_name, snap_id in sr:
    print(f"Updating '{snap_id}' for '{snap_name}' to {new_timestamp}")
    if not dry_run:
        res = ec2.create_tags(
            DryRun=dry_run,
            Resources=[
                snap_id,
            ],
            Tags=[
                {
                    'Key': 'jupyter-volume-stopping-time',
                    'Value': new_timestamp,
                },
            ],
        )
