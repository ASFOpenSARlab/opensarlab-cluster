#!/usr/bin/env python3

import datetime
import urllib

import escapism
import yaml
import boto3
from botocore.exceptions import ClientError

class DeleteSnapshot():

    def __init__(self):

        print("Checking for expired snapshots...")
        """
        with open("/etc/jupyterhub/custom/meta.yaml", 'r') as f:
            data = f.read()

        meta = yaml.safe_load(data)

        session = boto3.Session(aws_secret_access_key=meta['aws_secret_access_key'], aws_access_key_id=meta['aws_access_key_id'], region_name=meta['region_name'])
        self.cluster_name = meta['cluster_name']
        """
        session = boto3.Session(profile_name='jupyterhub')
        self.cluster_name = 'opensarlab-test'
        # List of threshold days since last activity.
        # On all but the last day an email is sent out warning about deletion of data and user deactivation.
        # On the last day, users are deactivated and user data is deleted.
        self.days_since_activity_thresholds = [30,44,46] 
        self.dry_run_disable = False
        self.dry_run_delete = True 
        self.dry_run_email = False

        self.cognito = session.client('cognito-idp')
        user_pools = self.cognito.list_user_pools(MaxResults=10)
        pool_id = [ u['Id'] for u in user_pools['UserPools'] if u['Name'] == self.cluster_name ][0]
        if not pool_id:
            raise Exception(f"Cognito user Pool '{self.cluster_name}' does not exist.")
        self.cognito.user_pool_id = pool_id

        self.ec2 = session.client('ec2')

        self.ses = session.client('ses')

    def _get_tags(self, snapshot, tag_key):
        return [v['Value'] for v in snapshot['Tags'] if v['Key'] == tag_key]

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
            #https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cognito-idp.html#CognitoIdentityProvider.Client.admin_disable_user
            response = self.cognito.admin_disable_user(
                UserPoolId=self.cognito.user_pool_id,
                Username=username
            )

            print(f"Disabled user {username}: {response}")
        else:
            print(f"Dry run: Did not disable user {username}.")

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
        #import pdb; pdb.set_trace()
        username = self._get_tags(snapshot, 'kubernetes.io/created-for/pvc/name')
        if len(username) == 0:
            raise Exception(f"Something went wrong with getting username for {snapshot['Tags']}")
        username = username[0].replace('claim-', '')
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
            today = datetime.datetime.now()
            days_inactive = today - datetime.datetime.strptime(volume_stopped_tag_date, '%Y-%m-%d %H:%M:%S.%f') 
            days_inactive = days_inactive.days

            user_email_address = self._cognito_get_email_address(username)

            send_email_after_days_inactive = self.days_since_activity_thresholds[0:-1]
            send_email_and_deactivate_after_days_inactive = self.days_since_activity_thresholds[-1]

            for d in send_email_after_days_inactive:
                if days_inactive == d:

                    num_days_left = send_email_and_deactivate_after_days_inactive - days_inactive
                    if num_days_left < 0:
                        num_days_left = 0
                    
                    email_meta = {
                        'SENDER': "uaf-jupyterhub-asf@alaska.edu",
                        'RECIPIENT': '<{user_email_address}>'.format(user_email_address=user_email_address),
                        'SUBJECT': "OpenSARlab Account Notifcation",
                        'BODY_HTML': """<html>
                            <head></head>
                            <body>
                            <p>The OpenSARlab account for {username} will be deactivated in {num_days_left} days. Any user data will deleted permanently.</p> 
                            <p>To stop this action, please sign back into your OpenSARlab account and start your server.</p>
                            <p>If you have any question please don't hesitate to email the <a href="mailto:uaf-jupyterhub-asf@alaska.edu">OpenSARlab Admin</a>.<p>
                            </body>
                            </html>""".format(username=username, num_days_left=num_days_left)
                    }
                    
                    self._send_email(email_meta)

            if days_inactive >= send_email_and_deactivate_after_days_inactive:

                # Disable user
                self._disable_user(username)

                # Delete remaining snapshot
                self._delete_snapshot(snapshot)

                email_meta = {
                    'SENDER': "uaf-jupyterhub-asf@alaska.edu",
                    'RECIPIENT': '<{user_email_address}>'.format(user_email_address=user_email_address),
                    'SUBJECT': "OpenSARlab Account Notifcation",
                    'BODY_HTML': """<html>
                        <head></head>
                        <body>
                        <p>The OpenSARlab account for {username} has been deactivated. All user data has been deleted permanently.</p>                         
                        <p>If you have any question please don't hesitate to email the <a href="mailto:uaf-jupyterhub-asf@alaska.edu">OpenSARlab Admin</a>.<p>
                        </body>
                        </html>""".format(username=username)
                }
                self._send_email(email_meta)

        except Exception as e:
            raise Exception(f"Username {username} had a snapshot issue. {e}")

    def _cognito_get_email_address(self, username):

        res = self.cognito.admin_get_user(
            UserPoolId=self.cognito.user_pool_id,
            Username=username
        )
        
        email_address = [ua['Value'] for ua in res['UserAttributes'] if ua['Name'] == 'email']
        if email_address is None:
            raise Exception(f"No email address set for user {username}")

        return email_address[0]

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

            for i, value in enumerate(hash_table):
                try:
                    print(f">>>> Checking snapshot #{i+1}")
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

def delete_snapshot():
    try:
        ds = DeleteSnapshot()
        snaps = ds.get_snapshots()
        ds.delete_unneeded_snapshots(snaps)

    except Exception as e:
        print(e)


if __name__ == "__main__":
    delete_snapshot()
