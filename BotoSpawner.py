import boto3

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
        self.aws_ec2 = boto3.resource('ec2')
        self.exit_value = 0

        # TODO remove testing code
        print('unset config value:\t' + self.image)
        try:
            print(self.invalid)
        except AttributeError as e:
            print(type(e))
            self.invalid = "valid"
            print(self.invalid)

        # TODO defaults here are overriding config file settings
        # default to the smallest machine running ubuntu server 18.04
        if not hasattr(self, 'image'):
            self.image = 'ami-0ac019f4fcb7cb7e6'
        if not hasattr(self, 'instance_type'):
            self.instance_type = 't2.nano'
        # TODO remove testing code
        print('security group defore default setup:\t' + self.security_group_id)
        # TODO move sec group setup to it's own method
        if not hasattr(self, 'security_group_id'):
            self.security_group_id = self.get_default_sec_group()

    def get_default_sec_group(self):
        # make sure there isn't already a default security group created
        created_groups = boto3.client('ec2').describe_security_groups(
            Filters=[
                {'Name': 'group-name', 'Values': ['default-jupyterhub-group']}
            ]
        )['SecurityGroups']
        # create default security group for the nodes if one does not exist
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
        # TODO specify subnet? potentially useful to limit IAM permissions for the hub
        # TODO create and specify launch template?
        # TODO is there a way to test this thoroughly without actually creating the instance?
        # TODO add security group. Preferably dynamically create a group allowing HTTP, HTTPS and ssh from only the hub
        image_id = self.image
        node = self.aws_ec2.create_instances(ImageId='ami-03b11c79dc4050fbf', MinCount=1, MaxCount=1,
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

                                             ]
                                             )
        if len(node) != 1:
            raise SpawnedTooManyEC2
        else:
            node = node[0]
            # TODO remove testing code
            print(f'node id:\t{node.instance_id}')
            self.node_id = node.instance_id
            # wait for the instance to be up
            ec2_client = boto3.client('ec2')
            wait_on_running = ec2_client.get_waiter('instance_running')
            wait_on_running.wait(InstanceIds=[self.node_id])

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

            # TODO for some reason this is None
            ip = self.aws_ec2.Instance(self.node_id).public_dns_name
            # TODO remove testing code
            print(f'IP Address:\t{ip}')
            # standard https port
            port = 443
            return ip, port

    @gen.coroutine
    def stop(self, now=False):
        self.aws_ec2.instances.filter(InstanceIds=[self.node_id]).terminate()
        wait_on_terminate = boto3.client('ec2').get_waiter('instance_terminated')
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