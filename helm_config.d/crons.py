import os

import z2jh

try:
    from crontab import CronTab

    working_directory = '/home/jovyan/crons'

    days_vol_inactive_till_termination = 5

    # Set metadata for use by cron scripts
    meta = [
        "---",
        "days_vol_inactive_till_termination: {days_vol_inactive_till_termination}",
        "namespace: jupyter",
        "cluster_name: {cluster_name}",
        "cognito_name: {cognito_name}",
        "region_name: {region_name}",
        "kubernetes_service_port: '{kubernetes_service_port}'",
        "kubernetes_service_host: {kubernetes_service_host}"
    ]
    meta = "\n".join(meta).format(
        days_vol_inactive_till_termination=days_vol_inactive_till_termination,
        region_name=z2jh.get_config('custom.AZ_NAME')[:-1],
        cluster_name=z2jh.get_config('custom.CLUSTER_NAME'),
        cognito_name=z2jh.get_config('custom.OAUTH_POOL_NAME'),
        kubernetes_service_port=os.environ.get('KUBERNETES_SERVICE_PORT'),
        kubernetes_service_host=os.environ.get('KUBERNETES_SERVICE_HOST')
    )
    with open(f"{working_directory}/meta.yaml", mode='w') as f:
        f.write(meta)

    # Make file executable
    os.chmod(f"{working_directory}/meta.yaml", 0o755)

    # Setup crontab for volume killer
    cron = CronTab(user='jovyan')

    # Lifecycle snapshot runs at 10 UTC, 1am AKST

    # Setup crontab for volume killer
    job2 = cron.new(command=f"python3 {working_directory}/delete_volumes.py > /proc/1/fd/1 2>&1")
    job2.hour.on(12)  # 12 UTC, 3am AKST
    job2.minute.on(0)
    job2.enable()

    # Setup crontab for snapshot killer
    job3 = cron.new(command=f"python3 {working_directory}/delete_snapshot.py > /proc/1/fd/1 2>&1")
    job3.hour.on(13)  # 13 UTC, 4am AKST
    job3.minute.on(0)
    job3.enable()

    cron.write()

except Exception as e:
    print("Something went wrong with starting the crons...")
    print(e)
