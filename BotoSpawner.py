import boto3
from time import sleep

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
        self.aws_ec2 = boto3.resource('ec2', region_name=self.region_name)
        self.ec2c = boto3.client('ec2', region_name=self.region_name)
        self.exit_value = 0
        # TODO hook warning logs into jupyterhub's logging system
        # TODO finish writing warning logs
        # TODO add default to create a default key if there would be a way to access that anyways
        if not hasattr(self, 'ssh_key'):
            self.ssh_key = None
            print('WARNING: no shh_key set you will not be able to ssh into nodes')
        if not hasattr(self, 'node_user'):
            self.node_user = 'ubuntu'
            print(f'WARNING: no node_user set, notebook server will attempt to set up as {self.node_user}')
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

    def create_startup_script(self):
        # TODO make this less system specific
        # shouldn't really be hardcoding the username of the user we want to run the notebook as
        # UserData commands are run as root by default
        # can workaround by finding a way to get the username automatically or by changing to sshing in to start the server after creating the ec2
        # TODO remove testing code
        startup_script = f'#!/bin/bash'
        startup_script = startup_script + '\nset -e -x'
        env = self.get_env()
        print('ENVIRONMENT VARIABLES:')
        for e in env.keys():
            startup_script = startup_script + f'\nexport {e}={env[e]}'
            print(f'\t{e}="{env[e]}"')
        # print(f'API TOKEN:\t"{self.api_token}"')
        # startup_script = startup_script + f'\nsudo --user ubuntu export JUPYTERHUB_API_TOKEN={self.api_token}'
        startup_script = startup_script + f'\n {self.startup_script}'
        startup_script = startup_script + f'\n {self.cmd[0]}'
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
        default_group = self.aws_ec2.create_security_group(
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
        node = self.aws_ec2.create_instances(ImageId=self.image_id, MinCount=1, MaxCount=1,
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
        if len(node) != 1:
            raise SpawnedTooManyEC2
        else:
            node = node[0]
            # TODO remove testing code
            print(f'node id:\t{node.instance_id}')
            self.node_id = node.instance_id
            # wait for the instance to be up

            # wait until the ec2 is up
            instance_state = 'not-started'
            while instance_state != 'running':
                sleep(15)
                # TODO split this into it's own function
                matching_instances = []
                for r in self.ec2c.describe_instances(InstanceIds=[self.node_id])['Reservations']:
                    for i in r['Instances']:
                        if i['InstanceId'] == self.node_id:
                            matching_instances.append(i)
                assert len(matching_instances) == 1
                instance_state = matching_instances[0]['State']['Name']

            # TODO make sure this is irrelevant
            # ssm = boto3.client('ssm')
            # notebook_state = 'not-sent'
            # print('node_id as of starting notebook:\t' + self.node_id)
            # while True:
            #     response = ssm.send_command(InstanceIds=[self.node_id],
            #                                 DocumentName='AWS-RunShellScript',
            #                                 # time to wait for command to start execution
            #                                 TimeoutSeconds=60,
            #                                 Parameters={
            #                                     'commands': ['jupyterhub-singleuser']
            #                                 },
            #                                 # TODO create bash script for starting singleuser process
            #                                 Comment='starts the jupyterhub-singleuser process on the node'
            #                                 )
            #     notebook_state = response['Command']['Status']
            #     if notebook_state == 'Success':
            #         break
            #     sleep(1)

            # TODO remove this once we're sure it's irrelevant
            # # wait for the network interface to be ready
            # interface_id = node.network_interfaces_attribute
            # # TODO remove testing code
            # print(interface_id)
            # if len(interface_id) != 1:
            #     raise WrongNumberNetworkInterfaces
            # else:
            #     interface_id = interface_id[0]
            #     wait_on_address = aws_ec2.get_waiter('network_interface_available')
            #     # wait_on_address.config.delay
            #     print(f'delay:\t{wait_on_address.config.delay}\nmax attempts:\t{wait_on_address.config.max_attempts}')
            #     wait_on_address.wait(NetworkInterfaceIds=[interface_id['NetworkInterfaceId']])

            # TODO if this breaks change back to old version
            node.load()
            ip = node.public_dns_name
            # ip = self.aws_ec2.Instance(self.node_id).public_dns_name
            # TODO remove testing code
            print(f'IP Address:\t{ip}')
            port = 8080
            return ip, port

    @gen.coroutine
    def stop(self, now=False):
        self.aws_ec2.instances.filter(InstanceIds=[self.node_id]).terminate()
        wait_on_terminate = self.ec2c.get_waiter('instance_terminated')
        self.exit_value = wait_on_terminate.wait(InstanceIds=[self.node_id])
        # instances = self.aws_ec2.instances.filter(InstanceIds=[self.node_id], Filters=[
        #     {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'shutting-down', 'stopping', 'stopped']}
        # ])
        # if len(instances) == 0:
        #     self.running =

    @gen.coroutine
    def poll(self):
        return self.exit_value

    def get_state(self):
        state = super(BotoSpawner, self).get_state()
        if self.node_id:
            state['node_id'] = self.node_id
        return state

    def load_state(self, state):
        super(BotoSpawner, self).load_state(state)
        if 'node_id' in state:
            self.node_id = state['node_id']

    def clear_state(self):
        super(BotoSpawner, self).clear_state()
        self.node_id = None


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