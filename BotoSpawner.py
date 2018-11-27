import boto3
import botocore
from os import environ as env
from time import sleep
from zipfile import ZipFile
import paramiko

from jupyterhub.spawner import Spawner
from tornado import gen


class SpawnedTooManyEC2(Exception):
    pass


class WrongNumberNetworkInterfaces(Exception):
    pass


class BotoSpawner(Spawner):

    def __init__(self, *args, **kwargs):
        super(BotoSpawner, self).__init__(*args, **kwargs)
        self.node_id = None
        if not hasattr(self, 'region_name'):
            self.region_name = 'us-east-1'
        self.ec2r = boto3.resource('ec2', region_name=self.region_name)
        self.ec2c = boto3.client('ec2', region_name=self.region_name)
        self.exit_value = 0
        # TODO hook warning logs into jupyterhub's logging system
        # TODO finish writing warning logs
        # set ssh key name to environment if not set
        # this avoids problems with overwriting keys when spawning multiple nodes
        if not hasattr(self, 'user_data_bucket'):
            print('WARNING: bucket for user data not set, data will not persist after server shutdown')
        if 'JUPYTERHUB_SSH_KEY' not in env:
            if hasattr(self, 'ssh_key'):
                env['JUPYTERHUB_SSH_KEY'] = self.ssh_key
            else:
                env['JUPYTERHUB_SSH_KEY'] = self.generate_ssh_key()
        self.ssh_key = env['JUPYTERHUB_SSH_KEY']

        if not hasattr(self, 'startup_script'):
            self.startup_script = ''
        # default to the smallest machine running ubuntu server 18.04
        if not hasattr(self, 'image_id'):
            self.image_id = 'ami-0ac019f4fcb7cb7e6'
            print(f'WARNING: no image_id set, using default bare ubuntu image, server creation will fail due to lacking jupyterhub-singleuser')
        if not hasattr(self, 'instance_type'):
            self.instance_type = 't2.nano'
        print('security group before default setup:\t' + self.security_group_id)
        if not hasattr(self, 'security_group_id'):
            self.security_group_id = self.get_default_sec_group()
        self.node = None

    def generate_ssh_key(self):
        key_name = 'Jupyterhub-Node-key'
        keys = self.ec2c.describe_key_pairs(Filters=[{'Name': 'key-name', 'Values': [f'{key_name}']}])
        if len(keys) > 0:
            self.ec2c.delete_key_pair(KeyName=f'{key_name}')
        key = self.ec2c.create_key_pair(KeyName=f'{key_name}')['KeyMaterial']
        # TODO if hub is running as non-root make sure it will have access to the key and the directory to save it
        with open(f'/etc/ssh/{key_name}.pem', 'w+') as key_file:
            key_file.write(key)
        return f'{key_name}.pem'


# TODO one of these will not be necessary
    def create_data_download_script(self):
        s3r = boto3.resource('s3')
        bucket = s3r.Bucket(self.user_data_bucket)
        files = bucket.objects.all()
        data_download_script = ''
        for file in files:
            if file.key == f'{self.user.name}.zip':
                # TODO finalize where user data should go on the nodes
                data_download_script = data_download_script + f'\n aws cp s3://{self.user_data_bucket}/{file.key} /$HOME'
                # TODO make sure that unzip will be installed on the node machines
                data_download_script = data_download_script + f'\n unzip /$HOME/{self.user.name}.zip -d /$HOME'
        return data_download_script

    def import_user_data(self):
        s3r = boto3.resource('s3')
        bucket = s3r.Bucket(self.user_data_bucket)
        files = bucket.objects.all()
        matches = []
        for file in files:
            if file.key == f'{self.user.name}.zip':
                matches.append(file.key)
        pkey = paramiko.RSAKey.from_private_key_file(f'/etc/ssh/{self.ssh_key}')
        ssh = paramiko.SSHClient()
        # TODO keep nodes in known hosts while they are up
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # TODO remove testing code
        print(f'PRIVATE KEY FILE:\t{self.ssh_key}')
        import subprocess
        print('NMAP PORT 22 BEFORE SSH CONNECTION')
        print(subprocess.check_output('nmap', self.node.public_dns_name, '-p', '22'))
        # TODO update for compatibility with individualized users
        with ssh.connect(hostname=self.node.public_dns_name, username='ubuntu', pkey=pkey) as connection:
            if matches:
                with ssh.open_sftp() as sftp:
                    filename = f'{self.user.name}.zip'
                    temp_location = f'/tmp/{filename}'
                    print('transferring user files to node')
                    for match in matches:
                        bucket.download_file(Key=filename, Filename=temp_location)
                        # TODO update for compatibility with individualized users
                        sftp.put(temp_location, f'/home/ubuntu/{filename}')
                        print('extracting files')
                        # TODO make sure that unzip will be installed on the node machines
                        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(f'unzip /home/ubuntu/{filename} -d /home/ubuntu')
                        print(ssh_stdout.read())
                        print(ssh_stderr.read())
            else:
                print('creating user directory')
                ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(f'mkdir /home/ubuntu/{self.user.name}')
                print(ssh_stdout.read())
                print(ssh_stderr.read())


# TODO one of these will not be necessary
    def create_data_upload_script(self):
        data_upload_script = f'\n zip /$HOME/{self.user.name}.zip /$HOME/{self.user.name}'
        data_upload_script = data_upload_script + f'\n aws s3 cp /#HOME/{self.user.name} s3://{self.user_data_bucket}/{self.user.name},zip'
        return data_upload_script

    def export_user_data(self):
        s3r = boto3.resource('s3')
        bucket = s3r.Bucket(self.user_data_bucket)
        filename = f'{self.user.name}.zip'
        temp_location = f'/tmp/{filename}'
        pkey = paramiko.RSAKey.from_private_key_file(f'/etc/ssh/{self.ssh_key}')
        ssh = paramiko.SSHClient()
        # TODO keep nodes in known hosts while they are up
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        with ssh.connect(hostname=self.node.public_dns_name, username='ubuntu', pkey=pkey) as connection:
            print('compressing files')
            ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(f'zip /home/ubuntu/{filename} /home/ubuntu/{self.user.name}')
            print(ssh_stdout)
            print(ssh_stderr)
            print('transferring files to s3')
            with ssh.open_sftp() as sftp:
                sftp.get(f'/home/ubuntu/{filename}', temp_location)
        bucket.upload_file(Filename=temp_location, Key=filename)


    def create_startup_script(self):
        # TODO make this less system specific
        # UserData commands are run as root by default
        # can workaround by finding a way to get the username automatically or by changing to sshing in to start the server after creating the ec2
        startup_script = f'#!/bin/bash'
        startup_script = startup_script + '\n set -e -x'
        # export relevant environment variables to the singleuser instance
        env = self.get_env()
        print('ENVIRONMENT VARIABLES:')
        for e in env.keys():
            startup_script = startup_script + f'\n export {e}={env[e]}'
        if hasattr(self, 'user_startup_script'):
            startup_script = startup_script + f'\n {self.user_startup_script}'
        startup_script = startup_script + f'\n {self.cmd}'
        return startup_script

    def get_default_sec_group(self):
        # make sure there isn't already a default security group created
        created_groups = self.ec2c.describe_security_groups(
            Filters=[
                {'Name': 'group-name', 'Values': ['default-jupyterhub-group']}
            ]
        )['SecurityGroups']
        # create default security group for the nodes if one does not exist already
        if len(created_groups) < 1:
            default_group_id = self.create_default_sec_group()
        else:
            assert len(created_groups) == 1
            default_group_id = created_groups[0]['GroupId']
        return default_group_id

    def create_default_sec_group(self):
        default_group = self.ec2r.create_security_group(
            Description='Default Jupyterhub Node Group',
            GroupName='default-jupyterhub-group'
        )
        default_group.authorize_egress(
            IpPermissions=[
                {
                    'IpProtocol': -1,
                    'IpRanges': [
                        {'CidrIp': '0.0.0.0/0', 'Description': 'allow all outgoing'}
                    ],
                    'Ipv6Ranges': [
                        {'CidrIpv6': '::/0', 'Description': 'allow all outgoing'}
                    ]
                }
            ]
        )
        default_group.authorize_ingress(
            CidrIp='0.0.0.0/0',
            IpPermissions=[
                {
                    'FromPort': 22,
                    'IpProtocol': 'tcp',
                    'IpRanges': [
                        {'CidrIp': '0.0.0.0/0', 'Description': 'allow ssh from all sources'}
                    ],
                    'Ipv6Ranges': [
                        {'CidrIpv6': '::/0', 'Description': 'allow ssh from all sources'}
                    ]
                },
                {
                    'FromPort': 80,
                    'IpProtocol': 'tcp',
                    'IpRanges': [
                        {'CidrIp': '0.0.0.0/0', 'Description': 'allow http from all sources'}
                    ],
                    'Ipv6Ranges': [
                        {'CidrIpv6': '::/0', 'Description': 'allow http from all sources'}
                    ]
                },
                {
                    'FromPort': 443,
                    'IpProtocol': 'tcp',
                    'IpRanges': [
                        {'CidrIp': '0.0.0.0/0', 'Description': 'allow https from all sources'}
                    ],
                    'Ipv6Ranges': [
                        {'CidrIpv6': '::/0', 'Description': 'allow https from all sources'}
                    ]
                }

            ]
        )
        return default_group.id

    @gen.coroutine
    def start(self):
        self.exit_value = None
        # compile shell commands to start up notebook server, also include any commands the user wants to run
        startup_script = self.create_startup_script()
        # TODO specify subnet? potentially useful to limit IAM permissions for the hub
        # TODO create and specify launch template?
        # TODO is there a way to test this thoroughly without actually creating the instance?
        # TODO add security group. Preferably dynamically create a group allowing HTTP, HTTPS and ssh from only the hub
        nodes = self.ec2r.create_instances(ImageId=self.image_id, MinCount=1, MaxCount=1,
                                          InstanceType=self.instance_type,
                                          NetworkInterfaces=[
                                                 {
                                                     'AssociatePublicIpAddress': True,
                                                     'DeleteOnTermination': True,
                                                     'Description': 'Address for access by the hub',
                                                     'DeviceIndex': 0,
                                                     'Groups': [self.security_group_id]
                                                 }
                                             ],
                                          # so you can tell what this is from the AWS console
                                          TagSpecifications=[
                                                 {'ResourceType': 'instance',
                                                  'Tags': [
                                                      {
                                                          'Key': 'Name',
                                                          'Value': f'asf-jupyterhub-node-{self.user.name}'
                                                      }
                                                  ]
                                                  }

                                             ],
                                          KeyName=self.ssh_key,
                                          UserData=startup_script
                                          )
        if len(nodes) != 1:
            raise SpawnedTooManyEC2
        else:
            self.node = nodes[0]
            # TODO remove testing code
            print(f'node id:\t{self.node.instance_id}')
            node_id = self.node.instance_id

            # wait until the ec2 is up
            # TODO make sure this only stops once the instance is actually accessible otherwise problems with sshing

            self.node.wait_until_running()

            self.node.load()
            # TODO remove debugging code
            print(f'INSTANCE STATE:\t{self.node.state["Name"]}')
            print(f'DNS NAME:\t{self.node.public_dns_name}')
            import subprocess
            print('NMAP PORT 22 AFTER WAITER:')
            print(subprocess.check_output(f'nmap {self.node.public_dns_name} -p 22'))

            if hasattr(self, 'user_data_bucket'):
                self.import_user_data()

            ip = self.node.public_dns_name
            # TODO remove testing code
            print(f'IP Address:\t{ip}')
            # this should match the port specified in cmd from jupyterhub_config.py I think
            port = 8080
            return ip, port

    @gen.coroutine
    def stop(self, now=False):
        node_id = self.node.instance_id

        if hasattr(self, 'user_data_bucket'):
            self.export_user_data()

        self.ec2r.instances.filter(InstanceIds=[node_id]).terminate()
        wait_on_terminate = self.ec2c.get_waiter('instance_terminated')
        self.exit_value = wait_on_terminate.wait(InstanceIds=[node_id])

    @gen.coroutine
    def poll(self):
        return self.exit_value

    def get_state(self):
        state = super(BotoSpawner, self).get_state()
        if self.node:
            state['node'] = self.node
        return state

    def load_state(self, state):
        super(BotoSpawner, self).load_state(state)
        if 'node' in state:
            self.node = state['node']

    def clear_state(self):
        super(BotoSpawner, self).clear_state()
        self.node = None


if __name__ == '__main__':
    spawn = BotoSpawner()
    spawn.image = 'ami-03b11c79dc4050fbf'
    spawn.instance_type = 't2.nano'
    from unittest import mock
    spawn.user = mock.MagicMock()
    spawn.user.name = 'm'
    instance = spawn.start()
    print(instance.public_ip_address)
    wait = input('waiting on you...')