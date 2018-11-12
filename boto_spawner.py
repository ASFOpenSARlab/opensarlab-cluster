import boto3

from jupyterhub.spawner import Spawner
from tornado import gen


class boto_spawner(Spawner):

    def __init__(self):
        super(boto_spawner, self).__init__()
        self.node_id = None

    @gen.coroutine
    def start(self):
        aws_ec2 = boto3.resource('ec2')
        # TODO create aws images for hub and nodes
        # TODO create and specify security group(probly ssh, http, https)
        # TODO specify subnet? potentially useful to limit IAM permissions for the hub
        # TODO create and specify launch template?
        node = aws_ec2.create_instances(ImageId='image_id', MinCount=1, MaxCount=1)
        self.node_id = node.instance_id
        ip = node.public_ip_address
        # standard https port
        port = 443
        return (ip, port)
