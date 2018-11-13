import boto3

from jupyterhub.spawner import Spawner
from tornado import gen


class BotoSpawner(Spawner):

    def __init__(self):
        super(BotoSpawner, self).__init__()
        self.node_id = None
        self.aws_ec2 = boto3.resource('ec2')
        self.exit_value = 0
        self.client = boto3.client('ec2')
        self.wait_on_terminate = self.client.get_waiter('instance_terminated')
        self.wait_on_running = self.client.get_waiter('instance_running')

    @gen.coroutine
    def start(self):
        self.exit_value = None
        # TODO create aws images for hub and nodes
        # TODO create and specify security group(probly ssh, http, https)
        # TODO specify subnet? potentially useful to limit IAM permissions for the hub
        # TODO create and specify launch template?
        image_id = self.user_options.get('image')
        node = self.aws_ec2.create_instances(ImageId=image_id, MinCount=1, MaxCount=1)
        self.node_id = node.instance_id
        self.wait_on_running.wait(InstanceIds=[self.node_id])
        print(self.node_id)
        ip = node.public_ip_address
        # standard https port
        port = 443
        return (ip, port)

    @gen.coroutine
    def stop(self, now=False):
        self.aws_ec2.instances.filter(InstanceIds=[self.node_id]).terminate()
        self.exit_value = self.wait_on_terminate.wait(InstanceIds=[self.node_id])
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
    spawner = BotoSpawner()
    spawner.start()
