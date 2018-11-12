import boto3

from jupyterhub.spawner import Spawner
from tornado import gen


class boto_spawner(Spawner):

    def __init__(self):
        super(boto_spawner, self).__init__()
        self.node_id = None
        self.aws_ec2 = boto3.resource('ec2')
        self.running = 0
        self.wait_on_terminate = boto3.client('ec2').get_waiter('instance_terminated')

    @gen.coroutine
    def start(self):
        self.running = None
        # TODO create aws images for hub and nodes
        # TODO create and specify security group(probly ssh, http, https)
        # TODO specify subnet? potentially useful to limit IAM permissions for the hub
        # TODO create and specify launch template?
        node = self.aws_ec2.create_instances(ImageId='image_id', MinCount=1, MaxCount=1)
        self.node_id = node.instance_id
        print(self.node_id)
        ip = node.public_ip_address
        # standard https port
        port = 443
        return (ip, port)

    @gen.coroutine
    def stop(self, now=False):
        self.aws_ec2.instances.filter(InstanceIds=[self.node_id]).terminate()
        exit = self.wait_on_terminate.wait(InstanceIds=[self.node_id])
        self.running = exit
        # instances = self.aws_ec2.instances.filter(InstanceIds=[self.node_id], Filters=[
        #     {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'shutting-down', 'stopping', 'stopped']}
        # ])
        # if len(instances) == 0:
        #     self.running =

    @gen.coroutine
    def poll(self):
        return self.running



if __name__ == '__main__':
    spawner = boto_spawner()
    spawner.start()