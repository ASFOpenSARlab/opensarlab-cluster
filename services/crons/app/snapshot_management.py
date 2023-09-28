
from pprint import pformat
import argparse
import logging
from datetime import datetime, timezone, timedelta

import boto3
import requests
import escapism

from opensarlab.auth import encryptedjwt

class BadTimeTagsException(Exception):
    """ If the time tags are bad or in the wrong order """

class SnapshotManagement():

    def __init__(
            self, 
            lab_short_name: str,
            days_after_server_stop_till_warning_email: list,
            days_after_server_stop_till_deletion_email: int,
            utc_hour_of_day_snapshot_cron_runs: int,
            cluster_name: str,
            portal_domain: str,
            aws_region: str,
            aws_profile: str=None,
            verbose: bool=False, 
            dry_run: bool=False
        ):

        if verbose:
            logging_level = logging.DEBUG
        else:
            logging_level = logging.INFO
        logging.basicConfig(format='%(asctime)s %(levelname)s (%(lineno)d) - %(message)s', level=logging_level)
        self.log = logging.getLogger(__name__)

        if aws_profile:
            session = boto3.Session(region_name=aws_region, profile_name=aws_profile)
        else:
            session = boto3.Session(region_name=aws_region)

        self.ec2 = session.client('ec2')
        self.cluster_name = cluster_name
        self.lab_short_name = lab_short_name
        self.portal_domain = portal_domain
        self.days_after_server_stop_till_warning_email = [int(e) for e in days_after_server_stop_till_warning_email.strip('[').strip(']').split(',')]
        self.days_after_server_stop_till_deletion_email = days_after_server_stop_till_deletion_email
        self.utc_hour_of_day_snapshot_cron_runs = utc_hour_of_day_snapshot_cron_runs
        self.dry_run = dry_run

        self.log.info(f"""Checking snapshots with
            cluster: '{self.cluster_name}',
            lab short name: '{self.lab_short_name},
            days after server stop till warning email: '{self.days_after_server_stop_till_warning_email}',
            days after server stop till deletion email: '{self.days_after_server_stop_till_deletion_email}',
            hour (utc) that the cron runs: '{self.utc_hour_of_day_snapshot_cron_runs}',
            region: '{aws_region}',
            profile: '{aws_profile}',
            verbose: {verbose},
            dry run: {self.dry_run}
        """)
 
    def _str_to_datetime(self, date_str: str, date_format: str='%Y-%m-%d %H:%M:%S+00:00') -> datetime:
        return datetime.strptime(date_str, date_format).replace(tzinfo=timezone.utc)

    def _get_tags(self, resource: dict, key: str) -> list:
        val = [v['Value'] for v in resource['Tags'] if v['Key'] == key]

        if not val:
            val = ['']

        return str(val[0])

    def _get_username_from_snapshot(self, snapshot) -> str:
        pvc_name = self._get_tags(snapshot, 'kubernetes.io/created-for/pvc/name')
        if not pvc_name.startswith('claim-'):
            if pvc_name == 'hub-db-dir':
                self.log.warning(f"Snapshot {snapshot['SnapshotId']} is a Database volume. Do not delete. Returning blank username ''")
            else:
                self.log.warning(f"Snapshot {snapshot['SnapshotId']}. Tag 'kubernetes.io/created-for/pvc/name' with pvc '{pvc_name}' does not start with 'claim-'. Returning blank username ''")
            return ''

        try:
            unescaped_username = pvc_name.replace('claim-', '')
            return escapism.unescape(unescaped_username, escape_char='-')
        except Exception as e:
            self.log.warning(f"Snapshot {snapshot['SnapshotId']}. Tag 'kubernetes.io/created-for/pvc/name' with pvc '{pvc_name}' could not be unescaped. Returning blank username ''")
            return ''

    def _post_email(self, payload: dict) -> int:
        data = encryptedjwt.encrypt(payload)
        url = f"{self.portal_domain}/user/email/send"

        if self.dry_run:
            self.log.info(f"url: {url}")
            self.log.info(f"payload: {payload}")
            self.log.warning(f"Dry run enabled. Will not send email.")
        else:
            r = requests.post(url=url, data=data, timeout=15)
            self.log.info(f"Sent post request to '{url}' with return status of {r.status_code}")
            r.raise_for_status

    def get_snapshots(self) -> list:
        snap = self.ec2.describe_snapshots(
            Filters=[
                {
                    'Name': 'tag:kubernetes.io/cluster/{0}'.format(self.cluster_name),
                    'Values': ['owned']
                },
                {
                    'Name': 'status',
                    'Values': ['completed']
                },
                {
                    'Name': 'tag:kubernetes.io/created-for/pvc/name',
                    'Values': ['*']
                }
            ],
            OwnerIds=['self']
        )
        return snap['Snapshots']

    def is_snapshot_valid(self, snapshot) -> bool:

        username = self._get_username_from_snapshot(snapshot)
        if not username:
            self.log.warning(f"Snapshot {snapshot['SnapshotId']}. Username not found. Skipping to next snapshot...")
            return False

        if self._get_tags(snapshot, 'do-not-delete'):
            self.log.warning(f"Snapshot {snapshot['SnapshotId']} has a 'Do-not-delete' tag. Skipping to next snapshot...")
            return False

        if self._get_tags(snapshot, 'jupyter-volume-stopping-time'):
            self.log.warning(f"Snapshot {snapshot['SnapshotId']} has a 'jupyter-volume-stopping-time' tag. This snapshot has a older schema and will not be deleted. Skipping to next snapshot...")
            return False

        if not self._get_tags(snapshot, 'server-stop-time'):
            self.log.warning(f"Snapshot {snapshot['SnapshotId']} does not have a 'server-stop-time' tag. Skipping to next snapshot...")
            return False

        if not self._get_tags(snapshot, 'volume-delete-time'):
            self.log.warning(f"Snapshot {snapshot['SnapshotId']} does not have a 'volume-delete-time' tag. Skipping to next snapshot...")
            return False

        if not self._get_tags(snapshot, 'snapshot-delete-time'):
            self.log.warning(f"Snapshot {snapshot['SnapshotId']} does not have a 'snapshot-delete-time' tag. Skipping to next snapshot...")
            return False

        self.log.info(f"Snapshot {snapshot['SnapshotId']} is valid.")
        return True

    def does_volume_still_exist(self, snapshot) -> bool:
        pvc_name = self._get_tags(snapshot, 'kubernetes.io/created-for/pvc/name')

        vol = self.ec2.describe_volumes(
            Filters=[
                {
                    'Name': 'tag:kubernetes.io/created-for/pvc/name',
                    'Values': [pvc_name]
                },
                {
                    'Name': 'tag:kubernetes.io/cluster/{0}'.format(self.cluster_name),
                    'Values': ['owned']
                }
            ]
        )

        if vol['Volumes']:
            self.log.warning(f"Volumes found for {pvc_name} in {self.cluster_name}. Skipping to next snapshot...")
            return True
        return False

    def delete_older_duplicates(self, snapshots: list) -> list:
        """
            Sometimes there might be an older duplicate of a snapshot. This could occur due to lifecyle managament
            abandoning a snapshot due to the deletion of it's original volume.

            Sort by pvc name. Delete the older snapshots if there are more than one. There should always be at least one snapshot
            present. The code will handle the one remaining snapshot as appropriate.

            Ignore if the `do-not-delete` tag is present. Since the hub db might have a duplicate volume, ignore `hub-db-dir`.

            return: list of snapshots with duplicates removed

        """
        reduced_snapshots = []
        hash_table = {}

        for snapshot in snapshots:
            # Create a hash table with the pvc name (which is presumed to be unique) as the key.
            # If subsequent entries match the hash key, there are duplicates.
            pvc = self._get_tags(snapshot, 'kubernetes.io/created-for/pvc/name')
            start_time: datetime = snapshot.get('StartTime', None)

            if pvc == 'hub-db-dir' or not start_time or (self._get_tags(snapshot, 'do-not-delete') or False):
                continue

            hash_key = str(abs(hash(pvc)))
            hash_value = { "snapshot": snapshot, "start_time": start_time }

            a = hash_table.get(hash_key, [])
            a.append(hash_value)
            hash_table[hash_key] = a

        for hash_value in hash_table.values():
            # Sort by start time, save the latest (or do-not-delete), delete the rest
            if len(hash_value) > 1:
                print("Hello")
            hash_value = sorted(hash_value, key=lambda e: e['start_time'], reverse=True)
            for i, value in enumerate(hash_value):
                if i == 0:
                    reduced_snapshots.append(value['snapshot'])
                else:
                    self.delete_snapshot(value['snapshot'])

        return reduced_snapshots

    def get_snapshot_times_from_snapshot_tags(self, snapshot: dict) -> dict:
        """
        From the snapshot tags, get all needed datetime stamps in datetime format.
        """

        time_of_last_server_stop = self._get_tags(snapshot, 'server-stop-time')
        time_of_volume_deletion = self._get_tags(snapshot, 'volume-delete-time')
        time_of_snapshot_deletion = self._get_tags(snapshot, 'snapshot-delete-time')

        dt_of_last_server_stop = self._str_to_datetime(time_of_last_server_stop)
        dt_of_volume_deletion = self._str_to_datetime(time_of_volume_deletion)
        dt_of_snapshot_deletion = self._str_to_datetime(time_of_snapshot_deletion)

        dts = {
            "dt_of_last_server_stop": dt_of_last_server_stop,
            "dt_of_volume_deletion": dt_of_volume_deletion,
            "dt_of_snapshot_deletion": dt_of_snapshot_deletion
        }

        self.log.info(f"Snapshot tag meta times: {pformat(dts)}")

        return dts

    def storage_timeline_status(self, snapshot_times: dict) -> str:

        dt_of_last_server_stop = snapshot_times['dt_of_last_server_stop']
        dt_of_volume_deletion = snapshot_times['dt_of_volume_deletion']
        dt_of_snapshot_deletion = snapshot_times['dt_of_snapshot_deletion']

        dt_of_last_server_stop_rounded = dt_of_last_server_stop.date()
        dt_of_volume_deletion_rounded = dt_of_volume_deletion.date()
        dt_of_snapshot_deletion_rounded = dt_of_snapshot_deletion.date()

        # The current time is somewhere between the volume getting deleted and when the snapshot is suppose to be deleted.
        # Since it's assumed that the cron runs once a day, round all times to the day on comparison.
        utc_day = datetime.now(timezone.utc).date()
        warning_days_rounded = [ dt_of_last_server_stop_rounded + timedelta(days=d) for d in list(self.days_after_server_stop_till_warning_email) ]
        email_deletion_day_rounded = dt_of_last_server_stop_rounded + timedelta(days=int(self.days_after_server_stop_till_deletion_email))

        # Make sure that dates are in the right order
        if dt_of_last_server_stop > dt_of_volume_deletion:
            raise BadTimeTagsException("Volume cannot be deleted before last server stop")

        if dt_of_volume_deletion > dt_of_snapshot_deletion:
            raise BadTimeTagsException("Snapshot cannot be deleted before accompying volume")

        actions = []

        if utc_day <= dt_of_last_server_stop_rounded:
            actions.append("volume being actively used right now")

        elif utc_day <= dt_of_volume_deletion_rounded:
            actions.append("timestamp before volume deletion time")

        elif utc_day <= dt_of_snapshot_deletion_rounded:

            if utc_day in warning_days_rounded:
                actions.append('send warning email')
            
            if utc_day == email_deletion_day_rounded:
                actions.append('send deletion email')
            
            if utc_day == dt_of_snapshot_deletion_rounded:
                actions.append('time to delete snapshot')

        elif utc_day > dt_of_snapshot_deletion_rounded:
            actions.append("snapshot should have already been deleted")

        else:
            actions.append("why are you seeing this?")

        return actions

    def send_warning_email(self, username: str, snapshot_times: dict) -> None:

        future_snapshot_crontime = f"{snapshot_times['dt_of_snapshot_deletion'].date()} {self.utc_hour_of_day_snapshot_cron_runs}:00 UTC"

        payload = {
            "to": {
                "username": username
            },
            "from": {
                "username": "osl-admin"
            },
            "cc": {
                "username": "osl-admin"
            },
            "subject": "OpenScienceLab Notification - Storage Warning",
            "html_body": f"""
                <p>
                    Hello {username},
                </p>
                <p>
                    In order to conserve space and costs for OpenScienceLab, user storage is set to be deleted 
                    after a period of inactivity.
                    Your user storage for lab '<b>{ self.lab_short_name }</b>' is set to be permanently 
                    deleted on { future_snapshot_crontime } unless further action is taken. 
                    Your OpenScienceLab username and password will not be changed.
                </p>
                <p>
                    To stop this from happening, log into <a href="{ self.portal_domain }">OpenScienceLab, 
                    click the <i>Go to lab</i> button for lab '{ self.lab_short_name }', 
                    then click on <i>Start My Server</i>.
                    No other action is required. Do not forget to stop your server when done.
                </p>
                <p>
                    Thank you,
                <br/>
                    Your OpenScienceLab Team
                </p>
            """
        }

        self._post_email(payload)

    def send_deletion_email(self, username: str) -> None:
        payload = {
            "to": {
                "username": username
            },
            "from": {
                "username": "osl-admin"
            },
            "cc": {
                "username": "osl-admin"
            },
            "subject": "OpenScienceLab Notification - Storage Deleted",
            "html_body": f"""
                <p>
                    Hello {username},
                </p>
                <p>
                    In order to conserve space and costs for OpenScienceLab, user storage is set to be deleted after a period of inactivity.
                    To enforce this, your storage for lab '<b>{self.lab_short_name}</b>' has been permanently deleted and cannot be retrieved.
                    Your OpenScienceLab username and password have not changed.
                </p>
                <p>
                    Thank you,
                <br/>
                    Your OpenScienceLab Team
                </p>
            """
        }

        self._post_email(payload)

    def send_error_report(self, errors_found: list) -> None:

        errors_report = ""
        for each_error in errors_found:
            errors_report += f"<tr> <td>{each_error['snapshot_id']}</td> <td>{each_error['error_msg']}</td> </tr>"

        payload = {
            "to": {
                "username": "osl-admin"
            },
            "from": {
                "username": "osl-admin"
            },
            "subject": "OpenScienceLab Snapshot CronJob Errors",
            "html_body": f"""
                <p>
                    The following are errors for lab '{self.cluster_name}' encountered while running the snapshot cronjob.
                </p>

                <table>
                    {errors_report}
                </table>
            """
        }

        self._post_email(payload)

    def delete_snapshot(self, snapshot: dict) -> None:
        self.log.info(f"Deleting snapshot {snapshot['SnapshotId']}")
        try:
            self.ec2.delete_snapshot(SnapshotId=snapshot['SnapshotId'], DryRun=self.dry_run)
        except Exception as e:
            if "DryRun" in str(e):
                self.log.warning(e)
            else:
                raise

    def is_good_snapshot(self, snapshot) -> bool:
        return self.is_snapshot_valid(snapshot) and not self.does_volume_still_exist(snapshot)

    def main(self) -> None:

        errors_found = []

        try:
            snapshots = self.get_snapshots()
            snapshots = self.delete_older_duplicates(snapshots)
        except Exception as e:
            errors_found.append({"snapshot_id": "N/A", "error_msg": str(e)})

        for snapshot in snapshots:
            try:
                if self.is_good_snapshot(snapshot):
                    username = self._get_username_from_snapshot(snapshot)
                    snapshot_times = self.get_snapshot_times_from_snapshot_tags(snapshot)
                    actions = self.storage_timeline_status(snapshot_times)

                    for action in actions:
                        self.log.info(f"Performing action '{action}' on {snapshot['SnapshotId']}")

                        if action == 'send warning email':
                            self.send_warning_email(username, snapshot_times)

                        elif action == 'send deletion email':
                            self.send_deletion_email(username)

                        elif action == 'time to delete snapshot':
                            self.delete_snapshot(snapshot)

                        elif action == 'snapshot should have already been deleted':
                            self.log.warning(f"{snapshot['SnapshotId']} is already past deletion time.")
                            raise Exception(f"Past snapshot deletion time. Something might have gone wrong with tagging. Snapshot times: {snapshot_times}")

                        elif action in [
                            'volume being actively used right now',
                            'timestamp before volume deletion time',
                            'why are you seeing this?']:
                            self.log.info(f"Noop action for snapshot {snapshot['SnapshotId']}: '{action}'")

            except Exception as e:
                # If there is an error, record that error and then move on to the next snapshot
                errors_found.append({"snapshot_id": str(snapshot['SnapshotId']), "error_msg": str(e)})

        if errors_found:
            self.send_error_report(errors_found)

        self.log.info("Done.")

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Check usage status of snapshots in lab deployment and send emails, remove users as needed.')
    parser.add_argument('--lab-short-name', help='Short name of lab.', dest='lab_short_name', required=True)
    parser.add_argument('--days-after-server-stop-till-warning-email', help='list of days from present till warning emails sent', dest='days_after_server_stop_till_warning_email', required=True)
    parser.add_argument('--days-after-server-stop-till-deletion-email', help='Integer day from present till deletion email sent', dest='days_after_server_stop_till_deletion_email')
    parser.add_argument('--utc-hour-of-day-snapshot-cron-runs', help='Integer hour (UTC) that the shapshot cron runs', dest='utc_hour_of_day_snapshot_cron_runs')
    parser.add_argument('--cluster-name', help='Cluster name (not short lab name)', dest='cluster_name', required=True)
    parser.add_argument('--portal-domain', help='Domain of Portal', dest='portal_domain', required=True)
    parser.add_argument('--region', help='AWS Region name', dest='aws_region', required=True)
    parser.add_argument('--profile', help='AWS profile largely for local development', dest='aws_profile', required=False)
    parser.add_argument('--verbose', help='Show debug messages', dest='verbose', action='store_true', required=False)
    parser.add_argument('--dry-run', help='Dry run email, removal, and deletions.', dest='dry_run', action='store_true', required=False)
    args = vars(parser.parse_args())

    vm = SnapshotManagement(**args)
    vm.main()
