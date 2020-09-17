#!/usr/bin/env python3

import datetime
import urllib
import time
import argparse

import escapism
import yaml
import boto3
from botocore.exceptions import ClientError

class DeleteSnapshot():

    def __init__(self, cluster=None, local=None, dry_run=True):
        print("Checking for expired snapshots...")

        if local:
            session = boto3.Session(profile_name='jupyterhub')
            self.cluster_name = cluster
        else:
            with open("/etc/jupyterhub/custom/meta.yaml", 'r') as f:
                data = f.read()

            meta = yaml.safe_load(data)

            session = boto3.Session(region_name=meta['region_name'])
            self.cluster_name = meta['cluster_name']
        print(f"Cluster name set to {self.cluster_name}")

        # List of threshold days since last activity.
        # On all but the last day an email is sent out warning about deletion of data and user deactivation.
        # On the last day, users are deactivated and user data is deleted.
        self.days_since_activity_thresholds = [30,37,41,43,45,46]

        print(f"Dry run set to {dry_run}")
        if dry_run == True: 
            self.dry_run_disable = True
            self.dry_run_delete = True 
            self.dry_run_email = True
        else:
            self.dry_run_disable = False
            self.dry_run_delete = False 
            self.dry_run_email = False

        self.cognito = session.client('cognito-idp')
        user_pools = self.cognito.list_user_pools(MaxResults=10)
        pool_id = [ u['Id'] for u in user_pools['UserPools'] if u['Name'] == self.cluster_name ][0]
        if not pool_id:
            raise Exception(f"Cognito user Pool '{self.cluster_name}' does not exist.")
        self.cognito.user_pool_id = pool_id

        self.ec2 = session.client('ec2')

        self.ses = session.client('ses')

        self.all_cog_users = self._get_user_list()
        
    def _get_user_list(self):
        res = self.cognito.list_users(
                UserPoolId=self.cognito.user_pool_id,
                Limit=60
            )
        user_list = [u['Username'] for u in res['Users']]
        token = res.get('PaginationToken', None)

        while token:
            res = self.cognito.list_users(
                UserPoolId=self.cognito.user_pool_id,
                Limit=60, 
                PaginationToken=token
            )
            user_list.extend([u['Username'] for u in res['Users']])
            token = res.get('PaginationToken', None)
            
            if not token:
                break
        
        print(f"{len(user_list)} Cognito users found")
        return user_list

    def _get_tags(self, snapshot, tag_key):
        return [v['Value'] for v in snapshot['Tags'] if v['Key'] == tag_key]

    def _get_cog_username(self, username):

        user_list = [u for u in self.all_cog_users if username == u.lower()]
        if len(user_list) == 0:
            raise Exception(f"Username {username} not found in Cognito")

        elif len(user_list) >= 2:
            raise Exception(f"Username '{username}' matches more than one cognito name: {user_list}")

        else:
            print(f"Username '{username}' matches cognito name '{user_list[0]}'")
            return user_list[0] 

    def _volume_still_exists(self, pvc_name, snapshot):
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

        if not vol['Volumes']:
            print(f"No volumes found for {pvc_name} in {self.cluster_name}")
            return False 
        return True

    def _delete_snapshot(self, snapshot):
        if not self.dry_run_delete:
            if self._get_tags(snapshot, 'do-not-delete'):
                print("Do-not-delete tag found. Skipping...")
            else:
                print(f"**** Deleting {snapshot['SnapshotId']}")
                self.ec2.delete_snapshot(SnapshotId=snapshot['SnapshotId'], DryRun=False)
        else:
            print(f"Dry run: Did not delete snapshot {snapshot['SnapshotId']}")

    def _disable_user(self, username):
        if not self.dry_run_disable:
        
            cog_username = self._get_cog_username(username)

            if cog_username:
                #https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cognito-idp.html#CognitoIdentityProvider.Client.admin_disable_user
                res = self.cognito.admin_disable_user(
                    UserPoolId=self.cognito.user_pool_id,
                    Username=cog_username
                )

                print(f"Disabled user {cog_username}: {res}")
        else:
            print(f"Dry run: Did not disable user {cog_username}.")

    def _send_email(self, email_meta):
        if not self.dry_run_email:
            # Try to send the email.
            try:
                #Provide the contents of the email.
                response = self.ses.send_email(
                    Destination={
                        'ToAddresses': [
                            email_meta['RECIPIENT'],
                        ],
                    },
                    Message={
                        'Body': {
                            'Html': {
                                'Charset': "UTF-8",
                                'Data': email_meta['BODY_HTML'],
                            },
                            'Text': {
                                'Charset': "UTF-8",
                                'Data': "",
                            },
                        },
                        'Subject': {
                            'Charset': "UTF-8",
                            'Data': email_meta['SUBJECT'],
                        },
                    },
                    Source=email_meta['SENDER']
                )
            # Display an error if something goes wrong.	
            except ClientError as e:
                print(e.response['Error']['Message'])
            else:
                print(f"Email sent! Message ID: {response['MessageId']}")
        else:
            print(f"Dry run: Did not send email to {email_meta['RECIPIENT']}")

    def _send_email_if_expired_and_maybe_delete(self, snapshot):
        pvc_name = self._get_tags(snapshot, 'kubernetes.io/created-for/pvc/name')
        if len(pvc_name) == 0:
            raise Exception(f"Something went wrong with getting username for {snapshot['Tags']}")
        username = pvc_name[0].replace('claim-', '')
        if username == 'hub-db-dir':
            print("Database volume found. Do not delete. Skipping...")
            return

        # 'escapism' is the custom library used by JupyterHub to escape server names
        username = escapism.unescape(username, escape_char='-')
        print(f"Checking snapshot of {username} for expiration...")
        
        try:
            # Send email deletion warning and/or delete as needed
            if self._get_tags(snapshot, 'do-not-delete'):
                print("Do-not-delete tag found. Skipping...")
                return 

            volume_stopped_tag_date = self._get_tags(snapshot, 'jupyter-volume-stopping-time')
            if len(volume_stopped_tag_date) == 0:
                print("volume_stopped_tag_date is not present. Skipping...")
                return  
            volume_stopped_tag_date = volume_stopped_tag_date[0]
            today = datetime.datetime.utcnow()
            days_inactive = today - datetime.datetime.strptime(volume_stopped_tag_date, '%Y-%m-%d %H:%M:%S.%f') 
            days_inactive = days_inactive.days

            print(f"Days inactive ({days_inactive}) for username '{username}'")

            # Double-check if any volumes exist. If so, then something went wrong with volume delete or snapshot management.
            if self._volume_still_exists(pvc_name[0], snapshot):
                print(f"Volume still present for snapshot for {pvc_name}. Skipping...")
                return 

            user_email_address = self._cognito_get_email_address(username)

            only_email_threshold = self.days_since_activity_thresholds[0:-1]
            email_and_action_threshold = self.days_since_activity_thresholds[-1]

            if days_inactive in only_email_threshold:
                num_days_left = email_and_action_threshold - days_inactive
                if num_days_left < 0:
                    num_days_left = 0
                
                email_meta = {
                    'SENDER': "uaf-jupyterhub-asf@alaska.edu",
                    'RECIPIENT': '<{user_email_address}>'.format(user_email_address=user_email_address),
                    'SUBJECT': "OpenSARlab Account Notification",
                    'BODY_HTML': """<html>
                        <head></head>
                        <body>
                        <p>The OpenSARlab account for {username} will be deactivated in {num_days_left} days due to inactivity. Any user data will be permanently deleted.</p> 
                        <p>To stop this action, please sign back into your OpenSARlab account and start your server.</p>
                        <p>If you have any questions please don't hesitate to email the <a href="mailto:uaf-jupyterhub-asf@alaska.edu">OpenSARlab Admin</a>.<p>
                        </body>
                        </html>""".format(username=username, num_days_left=num_days_left)
                }
                
                self._send_email(email_meta)

            elif days_inactive >= email_and_action_threshold:

                # Disable user
                self._disable_user(username)

                # Delete remaining snapshot
                self._delete_snapshot(snapshot)

                email_meta = {
                    'SENDER': "uaf-jupyterhub-asf@alaska.edu",
                    'RECIPIENT': '<{user_email_address}>'.format(user_email_address=user_email_address),
                    'SUBJECT': "OpenSARlab Account Notification",
                    'BODY_HTML': """<html>
                        <head></head>
                        <body>
                        <p>The OpenSARlab account for {username} has been deactivated due to {days} days of inactivity. All user data has been permanently deleted and cannot be recovered.</p>                
                        <p>If you would like to activate your account or have any questions, please don't hesitate to email the <a href="mailto:uaf-jupyterhub-asf@alaska.edu">OpenSARlab Admin</a>.<p>
                        </body>
                        </html>""".format(username=username, days=email_and_action_threshold)
                }
                self._send_email(email_meta)

            else:
                print(f"Days inactive ({days_inactive}) do not match any thresholds ({self.days_since_activity_thresholds}). Not performing any action.")

        except Exception as e:
            raise Exception(f"Username {username} had a snapshot issue. {e}")

    def _cognito_get_email_address(self, username):

        cog_username = self._get_cog_username(username)

        if cog_username:
            res = self.cognito.admin_get_user(
                UserPoolId=self.cognito.user_pool_id,
                Username=cog_username
            )
            
            email_address = [ua['Value'] for ua in res['UserAttributes'] if ua['Name'] == 'email']
            if email_address is None:
                raise Exception(f"No email address set for user {username}:{cog_username}")

            return email_address[0]
        
        else:
            return None

    def get_snapshots(self):

        # Get snapshot
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

    def delete_unneeded_snapshots(self, snaps):

        if len(snaps) > 0:
            hash_table = {}
            for snap in snaps:
                # Create a hash table with the pvc name (which is presumed to be unique) as the key. Then we can sort out the older snapshots.
                pvc = self._get_tags(snap, 'kubernetes.io/created-for/pvc/name')[0]
                h = str(abs(hash(pvc)))
                try:
                    a = hash_table[h]
                    a.append(snap)
                    hash_table[h] = a
                except Exception:
                    hash_table[h] = [snap]

            first_before = time.time()
            for i, value in enumerate(hash_table):
                before = time.time()
                try:
                    print(f">>>> Checking snapshot #{i+1} about {time.time() - first_before} seconds since beginning")
                    snaps_hash = hash_table[value]

                    # Order duplicate snaps by day. It is assumed that the latest is the one wanted.
                    snaps_hash = sorted(snaps_hash, key=lambda s: s['StartTime'], reverse=True)
                    if len(snaps_hash) > 1:
                        print("Deleting extra snapshots...")
                        # Always keep the newest snapshot of the group
                        extra_snaps = snaps_hash[1:]
                        for s in extra_snaps:
                            self._delete_snapshot(s)
                    
                    snap = snaps_hash[0]
                    self._send_email_if_expired_and_maybe_delete(snap)

                except Exception as e:
                    print(f"Something went wrong with snapshot handling...{e}")    
                
                finally:
                    after = time.time()
                    print(f"It took about {after-before} seconds")

                    # ses.sendEmail is rated to 14 emails per second. Let's make sure we stay below that limit. Even if we don't always get there.
                    time.sleep(0.2)

def delete_snapshot(cluster='opensarlab', local=False, dry_run=False):
    try:
        ds = DeleteSnapshot(cluster, local, dry_run)
        snaps = ds.get_snapshots()
        ds.delete_unneeded_snapshots(snaps)

    except Exception as e:
        print(e)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster", default="opensarlab")
    parser.add_argument("--local", action="store_true", dest="local")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    args = parser.parse_args()

    delete_snapshot(args.cluster, args.local, args.dry_run)
