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
        # TODO hook warning logs into jupyterhub's logging system
        # TODO finish writing warning logs
        # generate ssh key and set the name to environment if not already set
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

        # set defaults for things that should be set in the config file
        if not hasattr(self, 'user_startup_script'):
            self.user_startup_script = ''
        if not hasattr(self, 'default_userdata_archive'):
            self.default_userdata_archive = None
        if not hasattr(self, 'image_id'):
            self.image_id = 'ami-0ac019f4fcb7cb7e6'
            print(f'WARNING: no image_id set, using default bare ubuntu image, server creation will fail due to lacking jupyterhub-singleuser')
        if not hasattr(self, 'instance_type'):
            self.instance_type = 't2.nano'
        print('security group before default setup:\t' + self.security_group_id)
        if not hasattr(self, 'security_group_id'):
            self.security_group_id = self.get_default_sec_group()
        if not hasattr(self, 'log_dir'):
            self.log_dir = '/var/log'
        self.node = None

    # create a new ssh key for access to the nodes in AWS return the AWS id
    # TODO this could cause errors if two hubs are running key_name should really be set on a per-hub basis
    def generate_ssh_key(self):
        """
        :return: string, the name of the new key as stored in AWS
        """
        key_name = 'Jupyterhub-Node-key'
        keys = self.ec2c.describe_key_pairs(Filters=[{'Name': 'key-name', 'Values': [f'{key_name}']}])
        if len(keys) > 0:
            self.ec2c.delete_key_pair(KeyName=f'{key_name}')
        key = self.ec2c.create_key_pair(KeyName=f'{key_name}')['KeyMaterial']
        # TODO if hub is running as non-root make sure it will have access to the key and the directory to save it
        with open(f'/etc/ssh/{key_name}.pem', 'w+') as key_file:
            key_file.write(key)
        return f'{key_name}'

    # connect to the node via paramiko and return that connected client
    def ssh_to_node(self):
        """
        :return: paramiko.client.SSHClient object with an open connection to the node
        """
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

    # download the user data folder from S3 and unzip it, if it doesn't exist create a new user data directory
    def import_user_data(self, connection):
        """

        :param connection: a paramiko.client.SSHClient object with an open ssh connection to the node
        :return: 0 for successful completion
        """
        s3r = boto3.resource('s3')
        bucket = s3r.Bucket(self.user_data_bucket)

        filename = f'{self.user.name}.zip'
        temp_location = f'/tmp/{filename}'

        # this code is really ugly, I could shift it around some but I'm not sure how to do it in a way that's actually less complicated
        # try to get their files, if we can't find them go to the default, if we can't find that then make them a new directory
        # any s3 error that's not a 404 we raise
        try:
            bucket.download_file(filename, temp_location)
        except boto_excep.ClientError as e:
            if e.response['Error']['Code'] == "404":
                if self.default_userdata_archive:
                    print('the requested file was not found, creating a default user directory')
                    try:
                        bucket.download_file(self.default_userdata_archive, temp_location)
                    except boto_excep.ClientError as e:
                        if e.response['Error']['Code'] == '404':
                            print('the default file was not found, creating a new user directory')
                            ssh_stdin, ssh_stdout, ssh_stderr = connection.exec_command(f'mkdir /home/ubuntu/{self.user.name}')
                            print(ssh_stdout.read().decode('ascii'))
                            print(ssh_stderr.read().decode('ascii'))
                        else:
                            raise
                else:
                    print('the requested file was not found and no default is set, creating a new user directory')
                    ssh_stdin, ssh_stdout, ssh_stderr = connection.exec_command(f'mkdir /home/ubuntu/{self.user.name}')
                    print(ssh_stdout.read().decode('ascii'))
                    print(ssh_stderr.read().decode('ascii'))
                    return 0
            else:
                raise
        with connection.open_sftp() as sftp:

            print('transferring user file to node')
            # TODO update for compatibility with individualized users
            sftp.put(temp_location, f'/home/ubuntu/{filename}')
            print('extracting files')
            # TODO finalize where user data should go on the nodes
            ssh_stdin, ssh_stdout, ssh_stderr = connection.exec_command(f'unzip {filename}')
            print(ssh_stdout.read().decode('ascii'))
            print(ssh_stderr.read().decode('ascii'))
            print('cleaning up archive')
            ssh_stdin, ssh_stdout, ssh_stderr = connection.exec_command(f'rm {filename}')
            print(ssh_stdout.read().decode('ascii'))
            print(ssh_stderr.read().decode('ascii'))
        return 0

    # zip up the user data directory and upload it to S3
    def export_user_data(self, connection):
        """

        :param connection: a paramiko.client.SSHClient object with an open ssh connection to the node
        :return: 0 for successful completion, -1 for failure
        """
        s3r = boto3.resource('s3')
        bucket = s3r.Bucket(self.user_data_bucket)
        filename = f'{self.user.name}.zip'
        temp_location = f'/tmp/{filename}'

        # make sure the folder is there
        check_in, check_out, check_err = connection.exec_command('ls /home/ubuntu')
        out = check_out.read()
        decoded = out.decode('ascii')
        print('OUT:')
        print(type(out))
        print('DECODED:')
        print(type(decoded))
        print(decoded)
        print('OUT_LIST:')
        out_list = decoded.split('\n')

        print(type(out_list))
        if self.user.name in out_list:
            print('compressing files')
            ssh_stdin, ssh_stdout, ssh_stderr = connection.exec_command(f'zip -r {filename} {self.user.name}')
            print(ssh_stdout.read().decode('ascii'))
            print(ssh_stderr.read().decode('ascii'))
            print('transferring files to s3')

            with connection.open_sftp() as sftp:
                sftp.get(f'/home/ubuntu/{filename}', temp_location)
            bucket.upload_file(Filename=temp_location, Key=filename)
            return 0
        else:
            print(f'no "{filename}" folder found')
            return -1

    # compile everything that needs to run for startup into one bash script to be run on the node
    def create_startup_script(self):
        """

        :return: string: a bash script that exports necessary environment variables, runs configured startup commands and starts the Notebook server
        """
        node_env = self.get_env()
        startup_commands = [f'#!/bin/bash', 'set -e -x']
        startup_commands += [f'export {e}={node_env[e]}' for e in node_env.keys()]
        startup_commands.append(self.user_startup_script)
        startup_commands.append(' '.join(self.cmd))
        startup_commands.append('set +e +x')
        startup_script= '\n'.join(startup_commands)
        print(f'SCRIPT:\n{startup_script}')
        return startup_script

    # get the default security group for the nodes from AWS, create one if it doesn't exist
    def get_default_sec_group(self):
        """
        :return: string: the AWS id of the default security group for JupyterHub nodes
        """
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

    # creates the default security group
    def create_default_sec_group(self):
        """
        :return: string: the AWS id of the created default security group for JupyterHub nodes
        """
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
                    'FromPort': 8080,
                    'IpProtocol': 'tcp',
                    'IpRanges': [
                        {'CidrIp': '0.0.0.0/0', 'Description': 'allow http from all sources'}
                    ],
                    'Ipv6Ranges': [
                        {'CidrIpv6': '::/0', 'Description': 'allow http from all sources'}
                    ]
                }

            ]
        )
        return default_group.id

    @gen.coroutine
    def start(self):
        self.exit_value = None
        # TODO add identifying tag to allow for tag based conditionals in Hub IAM Role
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

            # TODO waiting this way increases startup times by a couple of minutes, maybe try waiting on the network interface?
            # wait until the ec2 is accessible
            waiter = self.ec2c.get_waiter('instance_status_ok')
            waiter.wait(InstanceIds=[self.node.instance_id])
            self.node.load()

            connection = self.ssh_to_node()

            self.import_user_data(connection)

            startup_script = self.create_startup_script()

            with open('/tmp/jupyter_singleuser_script', 'w')as script:
                script.write(startup_script)

            with connection.open_sftp() as sftp:
                sftp.put('/tmp/jupyter_singleuser_script', '/tmp/startup_script', confirm=True)
            ssh_stdin, ssh_stdout, ssh_stderr = connection.exec_command('sudo chmod 755 /tmp/startup_script')
            print(ssh_stdout.read().decode('ascii'))
            print(ssh_stderr.read().decode('ascii'))
            # saves log file to /var/log/singleuser_output.txt
            ssh_stdin, ssh_stdout, ssh_stderr = connection.exec_command(f'sudo touch {self.log_dir}/singleuser_output.log')
            print(ssh_stdout.read().decode('ascii'))
            print(ssh_stderr.read().decode('ascii'))
            ssh_stdin, ssh_stdout, ssh_stderr = connection.exec_command(f'sudo chmod 666 {self.log_dir}/singleuser_output.log')
            print(ssh_stdout.read().decode('ascii'))
            print(ssh_stderr.read().decode('ascii'))
            ssh_stdin, ssh_stdout, ssh_stderr = connection.exec_command(f'. /tmp/startup_script &> {self.log_dir}/singleuser_output.log')
            print(ssh_stdout.read().decode('ascii'))
            print(ssh_stderr.read().decode('ascii'))

            connection.close()

            ip = self.node.public_dns_name
            # this should match the port specified in cmd from jupyterhub_config.py
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