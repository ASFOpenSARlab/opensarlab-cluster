#!/usr/bin/env python3

import datetime
import urllib

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
        self.dry_run = True

        self.cognito = session.client('cognito-idp')
        user_pools = self.cognito.list_user_pools(MaxResults=10)
        pool_id = [ u['Id'] for u in user_pools['UserPools'] if u['Name'] == self.cluster_name ][0]
        if not pool_id:
            raise Exception(f"Cognito user Pool '{self.cluster_name}' does not exist.")
        self.cognito.user_pool_id = pool_id

        self.ec2 = session.client('ec2')

        self.sns = session.client('sns')

    def _delete_snapshot(self, snapshot):
        if not self.dry_run:
            if [v['Value'] for v in snapshot['Tags'] if v['Key'] == 'do-not-delete']:
                print("Do-not-delete tag found. Skipping...")
            else:
                print(f"**** Deleting {snapshot['SnapshotId']}")
                self.ec2.delete_snapshot(SnapshotId=snapshot['SnapshotId'], DryRun=False)
        else:
            print(f"Dry run: Did not delete snapshot {snapshot['SnapshotId']}")

    def _disable_user(self, username):
        if not self.dry_run:
            #https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cognito-idp.html#CognitoIdentityProvider.Client.admin_disable_user
            response = self.cognito.admin_disable_user(
                UserPoolId=self.cognito.user_pool_id,
                Username=username
            )

            print(f"Disabled user {username}: {response}")
        else:
            print(f"Dry run: Did not disable user {username}.")

    def _send_email(self, send_to_address, subject, body_html):
      
        if not self.dry_run:
            # Try to send the email.
            try:
                #Provide the contents of the email.
                response = self.sns.send_email(
                    Destination={
                        'ToAddresses': [
                            send_to_address,
                        ],
                    },
                    Message={
                        'Body': {
                            'Html': {
                                'Charset': "UTF-8",
                                'Data': body_html,
                            },
                            'Text': {
                                'Charset': "UTF-8",
                                'Data': "",
                            },
                        },
                        'Subject': {
                            'Charset': "UTF-8",
                            'Data': subject,
                        },
                    },
                    Source=send_to_address
             
                )
            # Display an error if something goes wrong.	
            except ClientError as e:
                print(e.response['Error']['Message'])
            else:
                print("Email sent! Message ID:"),
                print(response['MessageId'])
        else:
            print(f"Dry run: Did not send email to {send_to_address}")

    def _send_email_if_expired_and_maybe_delete(self, snapshot):
        import pdb; pdb.set_trace()
        username = [v['Value'] for v in snapshot['Tags'] if v['Key'] == 'kubernetes.io/created-for/pvc/name']
        if len(username) == 0:
            raise Exception(f"Something went wrong with getting username for {snapshot['Tags']}")
        username = urllib.parse.unquote(username[0])
        
        try:
            volume_stopped_tag_date = [v['Value'] for v in snapshot['Tags'] if v['Key'] == 'jupyter-volume-stopping-time']
            if len(volume_stopped_tag_date) == 0:
                print("volume_stopped_tag_date is not present. Skipping...")
                return  
            volume_stopped_tag_date = volume_stopped_tag_date[0]
            today = datetime.datetime.now()
            days_inactive = today - datetime.datetime.strptime(volume_stopped_tag_date, '%Y-%m-%d %H:%M:%S.%f') 
            days_inactive = days_inactive.days

            send_to_address = self._cognito_get_email_address(username)

            send_email_if = self.days_since_activity_thresholds[0:-1]
            send_email_and_deactivate_if = self.days_since_activity_thresholds[-1]

            for d in send_email_if:
                if days_inactive == d:
                    email_subject = "OpenSARlab account notifcation"
                    email_body_html = "The OpenSARlab account for {username} will be deactivated in {num_days} days. Any user data will deleted permanently. To stop this action, please sign back into your OpenSARlab account."
                    self._send_email(send_to_address, email_subject, email_body_html)

            if days_inactive >= send_email_and_deactivate_if:

                # Disable user
                self._disable_user(username)

                # Delete remaining snapshot
                self._delete_snapshot(snapshot)

                email_subject = "OpenSARlab account notifcation"
                email_body_html = "The OpenSARlab account for {username} has been deactivated. All user data has been deleted permanently."
                self._send_email(send_to_address, email_subject, email_body_html)

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

        return email_address

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
                pvc = [v['Value'] for v in snap['Tags'] if v['Key'] == 'kubernetes.io/created-for/pvc/name'][0]
                h = str(abs(hash(pvc)))
                try:
                    a = hash_table[h]
                    a.append(snap)
                    hash_table[h] = a
                except Exception:
                    hash_table[h] = [snap]

            for i in hash_table:
                try:
                    snaps_hash = hash_table[i]
                    # Order duplicate snaps by day. It is assumed that the latest is the one wanted.
                    snaps_hash = sorted(snaps_hash, key=lambda s: s['StartTime'], reverse=True)
                    if len(snaps_hash) > 1:
                        # Always keep the newest snapshot of the group
                        extra_snaps = snaps_hash[1:]
                        for s in extra_snaps:
                            self._delete_snapshot(s)
                    
                    snap = snaps_hash[0]

                    # Send email deletion warning and/or delete as needed
                    if [v['Value'] for v in snap['Tags'] if v['Key'] == 'do-not-delete']:
                        print("Do-not-delete tag found. Skipping...")
                    else:
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
