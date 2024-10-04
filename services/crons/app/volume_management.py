#!/usr/bin/env python3

"""
python3 -m pip install boto3 kubernetes

"""

import argparse
import logging
import datetime

import requests
import boto3
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from opensarlab.auth import encryptedjwt

logging.basicConfig(
    format="%(asctime)s %(levelname)s (%(lineno)d) - %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)


def _send_error_report(
    errors_found: list,
    cluster_name: str,
    portal_domain: str,
    sso_token: str,
    dry_run: bool,
) -> None:
    errors_report = ""
    for each_error in errors_found:
        errors_report += f"<tr> <td>{each_error['volume_id']}</td> <td>{each_error['error_msg']}</td> </tr>"

    payload = {
        "to": {"username": "osl-admin"},
        "from": {"username": "osl-admin"},
        "subject": "OpenScienceLab Volume CronJob Errors",
        "html_body": f"""
            <p>
                The following are errors for lab '{cluster_name}' encountered while running the volume cronjob.
            </p>

            <table>
                {errors_report}
            </table>
        """,
    }

    data = encryptedjwt.encrypt(payload, sso_token=sso_token)
    url = f"{portal_domain}/user/email/send"

    if dry_run:
        log.info(f"url: {url}")
        log.info(f"payload: {payload}")
        log.warning(f"Dry run enabled. Will not send email.")
    else:
        r = requests.post(url=url, data=data, timeout=15)
        log.info(f"Sent post request to '{url}' with return status of {r.status_code}")
        r.raise_for_status


def _get_tags(resource: dict, key: str) -> list:
    val = [v["Value"] for v in resource["Tags"] if v["Key"] == key]

    if not val:
        val = [""]

    return str(val[0])


def delete_volumes(
    cluster_name: str,
    aws_region: str,
    dry_run: bool,
    aws_profile: str,
    ignore_snapshot_requirement: bool,
    portal_domain: str,
) -> None:
    errors_found = []

    try:
        log.info("Checking for expired volumes...")

        try:
            k8s_config.load_incluster_config()
        except:
            k8s_config.load_config()
        api = k8s_client.CoreV1Api()

        if aws_profile:
            session = boto3.Session(region_name=aws_region, profile_name=aws_profile)
        else:
            session = boto3.Session(region_name=aws_region)

        secrets_manager = session.client("secretsmanager")
        ec2 = session.client("ec2")

        log.info(f"Searching for volumes in cluster '{cluster_name}' to delete...")

        # Volumes currently in use are ignored. Only select available volumes.
        vols = ec2.describe_volumes(
            Filters=[
                {
                    "Name": "tag:kubernetes.io/cluster/{0}".format(cluster_name),
                    "Values": ["owned"],
                },
                {"Name": "tag:kubernetes.io/created-for/pvc/name", "Values": ["*"]},
                {"Name": "status", "Values": ["available"]},
            ]
        )

        vols = vols["Volumes"]

        log.info(f"Number of vols: {len(vols)}")
        if len(vols) == 0:
            vols = []

        log.info(f"Number of volumes found for '{cluster_name}': {len(vols)}")

        for vol in vols:
            vol_id = vol["VolumeId"]
            log.info(f"Checking volume {vol_id}...")

            # Get PVC name
            pvc_name = _get_tags(vol, "kubernetes.io/created-for/pvc/name")
            if not pvc_name:
                log.warning(
                    f"Volume '{vol_id}' not tagged 'kubernetes.io/created-for/pvc/name'. Skipping...."
                )
                continue

            # Do not delete the Hub DB!!
            if pvc_name == "hub-db-dir":
                log.warning(
                    f"Volume '{vol_id}' is tagged 'hub-db-dir' found. Skipping...."
                )
                continue

            # Do not delete if tagged as such
            if _get_tags(vol, "do-not-delete"):
                log.warning(f"Volume '{vol_id}' tagged 'do-not-delete'. Skipping....")
                continue

            # Get last stopped tags
            if _get_tags(vol, "jupyter-volume-stopping-time"):
                log.warning(
                    f"Volume '{vol_id}' is tagged with 'jupyter-volume-stopping-time' which is an old schema and is not useable. Skipping..."
                )
                continue

            # Get last stopped tags
            server_stop_time = _get_tags(vol, "server-stop-time")
            if not server_stop_time:
                log.warning(
                    f"Volume '{vol_id}' is not tagged with server_stop_time and is not useable. Skipping..."
                )
                continue
            try:
                server_stop_time = datetime.datetime.strptime(
                    server_stop_time, "%Y-%m-%d %H:%M:%S+00:00"
                )
            except ValueError as e:
                log.error(e)
                errors_found.append({"volume_id": str(vol_id), "error_msg": str(e)})
                continue

            # Get volume delete time
            volume_delete_time = _get_tags(vol, "volume-delete-time")
            if not volume_delete_time:
                log.warning(
                    f"Volume '{vol_id}' is not tagged with volume_delete_time and is not useable. Skipping..."
                )
                continue
            try:
                volume_delete_time = datetime.datetime.strptime(
                    volume_delete_time, "%Y-%m-%d %H:%M:%S+00:00"
                )
            except ValueError as e:
                log.error(e)
                errors_found.append({"volume_id": str(vol_id), "error_msg": str(e)})
                continue

            # If the last time the server stopped was after the volume deletion time, then something is wrong with the tagging.
            # The volume deletion time should always be greater.
            if server_stop_time > volume_delete_time:
                log.warning(
                    f"Volume '{vol_id}' has a volume_delete_time value younger than server stopping time. Skipping..."
                )
                continue

            if ignore_snapshot_requirement:
                has_valid_snapshot = True  # Pretend that there is a snapshot so the volume will be deleted anyway
                log.info(
                    "Ignoring snapshots. Volume will be possibly deleted even if snapshot is not present."
                )
            else:
                # Get snapshot
                snap = ec2.describe_snapshots(
                    Filters=[
                        {
                            "Name": "tag:kubernetes.io/created-for/pvc/name",
                            "Values": ["{0}".format(pvc_name)],
                        },
                        {
                            "Name": "tag:kubernetes.io/cluster/{0}".format(
                                cluster_name
                            ),
                            "Values": ["owned"],
                        },
                        {"Name": "status", "Values": ["completed"]},
                    ],
                    OwnerIds=["self"],
                )
                snap = snap["Snapshots"]

                has_valid_snapshot = False
                if len(snap) == 0:
                    log.warning("No snapshots have been found.")
                else:
                    # If the snapshot lifecycle policy fails, daily snapshots will stop and snapshots will slowly age out and get out of sync with the volumes.
                    # If someone later stops their volumes for more than the delete threshold, then that volume will be deleted.
                    # Since the snapshot is out of sync, restoring from the snapshot will give bad data.
                    # To avoid this, don't delete volumes when all the corresponding snapshots are too old.

                    days_till_too_old = 2

                    snapshots_too_old = [
                        True
                        for s in snap
                        if s["StartTime"]
                        < datetime.datetime.now(datetime.timezone.utc)
                        - datetime.timedelta(days=days_till_too_old)
                    ]
                    if len(snapshots_too_old) == len(snap):
                        log.info(
                            f"No snapshots found newer than {days_till_too_old} days old. Will not delete volume '{vol_id}'."
                        )
                    else:
                        has_valid_snapshot = True

            # Get time difference between now and when the volume is suppose to be deleted.
            time_diff = volume_delete_time - datetime.datetime.now()
            log.info(f"Days till volume is too old: {time_diff}")
            do_deactivate = time_diff.total_seconds() < 0
            is_available = vol["State"] == "available"

            log.info(
                f"do_deactivate: {do_deactivate}, has_valid_snapshots: {has_valid_snapshot}, is_available: {is_available}"
            )
            if is_available and has_valid_snapshot and do_deactivate:
                # Delete PVC
                log.info(f"Delete pvc '{pvc_name}'")
                try:
                    if dry_run:
                        log.info("Dry run. Skipping deletion of pvc...")
                    else:
                        namespace = "jupyter"
                        api.delete_namespaced_persistent_volume_claim(
                            body=k8s_client.V1DeleteOptions(),
                            name=pvc_name,
                            namespace=namespace,
                        )
                except ApiException as e:
                    log.warning("Did not delete volume...")
                    log.error(e)
                    errors_found.append({"volume_id": str(vol_id), "error_msg": str(e)})
                    continue

    except Exception as e:
        log.error(e)
        errors_found.append({"volume_id": "N/A", "error_msg": str(e)})

    if errors_found:
        _sso_token = secrets_manager.get_secret_value(
            SecretId=f"sso-token/{aws_region}-{cluster_name}"
        )
        _send_error_report(
            errors_found, cluster_name, portal_domain, _sso_token, dry_run
        )

    log.info("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check usage status of volumes in lab deployment and delete as needed."
    )
    parser.add_argument(
        "--cluster-name",
        help="Cluster name (not short lab name)",
        dest="cluster_name",
        required=True,
    )
    parser.add_argument(
        "--region", help="AWS Region name", dest="aws_region", required=True
    )
    parser.add_argument(
        "--portal-domain",
        help="Domain of Portal (including https://)",
        dest="portal_domain",
        required=True,
    )
    parser.add_argument(
        "--profile",
        help="AWS profile largely for local development",
        dest="aws_profile",
        required=False,
    )
    parser.add_argument(
        "--dry-run",
        help="Dry run email, removal, and deletions.",
        dest="dry_run",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "--ignore-snapshot-requirement",
        help="Ignore if backup snapshot exists and possibly delete volume anyway.",
        dest="ignore_snapshot_requirement",
        action="store_true",
        required=False,
    )
    args = vars(parser.parse_args())

    delete_volumes(**args)
