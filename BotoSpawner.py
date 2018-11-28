import boto3
from botocore import exceptions as boto_excep
from os import environ as env
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
        self.node_ssh = None
        # TODO hook warning logs into jupyterhub's logging system
        # TODO finish writing warning logs
        # set ssh key name to environment if not set
        # this avoids problems with overwriting keys when spawning multiple nodes
        if not hasattr(self, 'user_data_bucket'):
            print('WARNING: bucket for user data not set, data will not persist after server shutdown')
            self.user_data_bucket = None
        if 'JUPYTERHUB_SSH_KEY' not in env:
            if hasattr(self, 'ssh_key'):
                env['JUPYTERHUB_SSH_KEY'] = self.ssh_key
            else:
                env['JUPYTERHUB_SSH_KEY'] = self.generate_ssh_key()
        self.ssh_key = env['JUPYTERHUB_SSH_KEY']

        if not hasattr(self, 'user_startup_script'):
            self.user_startup_script = ''
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
        return f'{key_name}'


    def ssh_to_node(self):
        try:
            pkey = paramiko.RSAKey.from_private_key_file(f'/etc/ssh/{self.ssh_key}.pem')
        except Exception as e:
            print('Exception in loading private key')
            print(e)
            return -1
        ssh = paramiko.SSHClient()
        # TODO keep nodes in known hosts while they are up instead of this
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # TODO update for compatibility with individualized users
        try:
            ssh.connect(hostname=self.node.public_dns_name, username='ubuntu', pkey=pkey)
        except Exception as e:
            print('Exception in connecting to node')
            print(e)
            return -2
        return ssh

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

    def import_user_data(self, connection):
        s3r = boto3.resource('s3')
        bucket = s3r.Bucket(self.user_data_bucket)

        filename = f'{self.user.name}.zip'
        temp_location = f'/tmp/{filename}'
        try:
            bucket.download_file(filename, temp_location)
        except boto_excep.ClientError as e:
            if e.response['Error']['Code'] == "404":
                print("The requested file was not found, creating a user directory")
                ssh_stdin, ssh_stdout, ssh_stderr = connection.exec_command(f'mkdir /home/ubuntu/{self.user.name}')
                print(ssh_stdout.read())
                print(ssh_stderr.read())
                return 0
            else:
                raise
        with connection.open_sftp() as sftp:

            print('transferring user file to node')
            # TODO update for compatibility with individualized users
            sftp.put(temp_location, f'/home/ubuntu/{filename}')
            print('extracting files')
            # TODO make sure that unzip will be installed on the node machines
            ssh_stdin, ssh_stdout, ssh_stderr = connection.exec_command(f'unzip /home/ubuntu/{filename} -d /home/ubuntu')
            print(ssh_stdout.read())
            print(ssh_stderr.read())
            return 0


# TODO one of these will not be necessary
    def create_data_upload_script(self):
        data_upload_script = f'\n zip /$HOME/{self.user.name}.zip /$HOME/{self.user.name}'
        data_upload_script = data_upload_script + f'\n aws s3 cp /#HOME/{self.user.name} s3://{self.user_data_bucket}/{self.user.name},zip'
        return data_upload_script

    def export_user_data(self, connection):
        s3r = boto3.resource('s3')
        bucket = s3r.Bucket(self.user_data_bucket)
        filename = f'{self.user.name}.zip'
        temp_location = f'/tmp/{filename}'

        # make sure the folder is there
        check_in, check_out, check_err = connection.exec_command('ls /home/ubuntu')
        if self.user.name in check_out.read().split('\n'):
            print('compressing files')
            ssh_stdin, ssh_stdout, ssh_stderr = connection.exec_command(f'zip /home/ubuntu/{filename} /home/ubuntu/{self.user.name}')
            print(ssh_stdout)
            print(ssh_stderr)
            print('transferring files to s3')

            with connection.open_sftp() as sftp:
                sftp.get(f'/home/ubuntu/{filename}', temp_location)
            bucket.upload_file(Filename=temp_location, Key=filename)
            return 0
        else:
            print(f'no "{filename}" folder found')
            return -1

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
        startup_script = startup_script + '\n'
        for arg in self.cmd:
            startup_script = startup_script + f'{arg} '
        print(f'CMD:\t{self.cmd}')
        print(f'SCRIPT:\t{startup_script}')
        return startup_script

    def compile_startup_commands(self):
        environ = self.get_env()
        commands = []
        commands.append('set -e -x')
        for e in environ:
            commands.append(f'export {e}={env[e]}')
        if hasattr(self, 'user_startup_script'):
            commands.append(self.user_startup_script)
        cmd = ''
        for arg in self.cmd:
            cmd = cmd + f'{arg} '
        cmd = cmd + 'touch singleuser_output.txt'
        cmd = cmd + ' &> /home/ubuntu/singleuser_output.txt'
        commands.append(cmd)
        print(f'CMD:\t{self.cmd}')
        print(f'ALL COMMANDS:\t{commands}')
        return commands

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
                                          )
        if len(nodes) != 1:
            raise SpawnedTooManyEC2
        else:
            self.node = nodes[0]
            node_id = self.node.instance_id

            # TODO this is probably waiting for longer than it needs to, it might be worth trying to wait on the network interface instead
            # wait until the ec2 is accessible
            waiter = self.ec2c.get_waiter('instance_status_ok')
            waiter.wait(InstanceIds=[self.node.instance_id])
            self.node.load()

            connection = self.ssh_to_node()

            self.import_user_data(connection)
            commands = self.compile_startup_commands()
            for c in commands:
                connection.exec_command(c)

            connection.close()

            ip = self.node.public_dns_name
            # this should match the port specified in cmd from jupyterhub_config.py I think
            port = 8080
            return ip, port

    @gen.coroutine
    def stop(self, now=False):

        if self.user_data_bucket:
            connection = self.ssh_to_node()
            self.export_user_data(connection)
            connection.close()

        self.ec2r.instances.filter(InstanceIds=[self.node.instance_id]).terminate()
        wait_on_terminate = self.ec2c.get_waiter('instance_terminated')
        self.exit_value = wait_on_terminate.wait(InstanceIds=[self.node.instance_id])

    @gen.coroutine
    def poll(self):
        return self.exit_value

    def get_state(self):
        state = super(BotoSpawner, self).get_state()
        if self.node:
            state['node_id'] = self.node.id
        return state

    def load_state(self, state):
        super(BotoSpawner, self).load_state(state)
        if 'node_id' in state:
            node_id = state['node_id']
            self.node = self.ec2r.Instance(node_id)

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