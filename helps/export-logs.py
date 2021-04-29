from datetime import datetime

import boto3
import botocore
import colorama

print(f"\n\n\n***************** Starting export logs at {datetime.now()}")

############ Config Settings #####

migrate_users = False
migrate_snapshots = True

old_profile = 'jupyterhub'
old_cluster = 'opensarlab'
old_region = 'us-east-1'

new_profile = 'osl-e'
new_cluster = 'osl-daac-cluster'
new_region = 'us-east-1'

##################################

colorama.init(autoreset=True)

old_session = boto3.Session(profile_name=old_profile)
new_session = boto3.Session(profile_name=new_profile)

logs = old_session.client('logs')
log_groups = logs.describe_log_groups()

jan_1_2019 = int(datetime.strptime('01.01.2019', '%d.%m.%Y').timestamp() * 1000)
apr_21_2021 = int(datetime.strptime('21.04.2021', '%d.%m.%Y').timestamp() * 1000)

s3_bucket = 'old-osl-daac-cluster-logs'

is_running = False
are_done_list = []

for status in ['COMPLETED', 'CANCELLED', 'FAILED', 'PENDING_CANCEL', 'PENDING', 'RUNNING']:
    print(f"\nCurrent {status} exports...")
    export_tasks = logs.describe_export_tasks(
        statusCode=status
    )
    exportTasks = export_tasks['exportTasks']
    for r in exportTasks:
        print(r)
        if status in ['PENDING', 'RUNNING']:
            is_running = True
        if status in ['COMPLETED', 'PENDING_CANCEL', 'CANCELLED']:
            are_done_list.append(r['taskName'])

if is_running:
    print(f"\n!!!!! Export with running/pending found. Can only have one running at one time. Try again later.")
    exit()

print(f"\n\nExports done (COMPLETED, PENDING_CANCEL, CANCELLED) include {are_done_list} \n\n")

for group in log_groups['logGroups']:

    name = group['logGroupName']
    print(f"*** Checking log name '{name}'")

    prefix = name.replace('/', '-')
    if prefix[0] == '-':
        prefix = prefix[1:]

    if prefix in are_done_list:
        print(f"   Log name '{name}'' is already done. Checking another...")
        continue

    try:
        response = logs.create_export_task(
            taskName=prefix,
            logGroupName=name,
            fromTime=jan_1_2019,
            to=apr_21_2021,
            destination=s3_bucket,
            destinationPrefix=prefix
        )
        print(f"    Exporting log name '{name}' to '{s3_bucket}/{prefix}'")
        exit()
    except Exception as e:
        print(f"!!! Export error: {e}")
