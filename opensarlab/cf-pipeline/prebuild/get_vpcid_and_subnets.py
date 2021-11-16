
import argparse

import boto3
import yaml

def which_subnet_is_az(subnets, az_postfix):
    
    for subid, az in subnets:
        if az_postfix in az:
            active_subnet = subid
        else:
            other_subnet = subid
    
    return active_subnet, other_subnet

def main(region_name, profile_name, cluster_name, append_parameters_to, az_postfix):

    session = None 
    try:
        session = boto3.session.Session(region_name=region_name, profile_name=profile_name)
    except:
        session = boto3.session.Session(region_name=region_name)

    eks = session.client('eks')
    ec2 = session.client('ec2')
    
    active_subnet = None
    other_subnet = None
    vpcid = None
    
    try:
        response = eks.describe_cluster(name=cluster_name)
        subnets = response['cluster']['resourcesVpcConfig']['subnetIds']
        vpcid = response['cluster']['resourcesVpcConfig']['vpcId']
        
        response = ec2.describe_subnets(
            SubnetIds=subnets
        )

        all_subnets = [(s['SubnetId'], s['AvailabilityZone']) for s in response['Subnets']]
        
        # Which subnet is -d and which is random?
        active_subnet, other_subnet = which_subnet_is_az(all_subnets, az_postfix)
        
    except eks.exceptions.ResourceNotFoundException as e:
        print("Resource not found: ", e)

        # Use default VPC
        response = ec2.describe_vpcs(
            Filters=[
                {
                    'Name': 'isDefault',
                    'Values': [
                        'true'
                    ]
                },
            ]
        )
    
        default_vpcid = response['Vpcs'][0]['VpcId']
        
        response = ec2.describe_subnets(
            Filters=[
                {
                    'Name': 'vpc-id',
                    'Values': [
                        default_vpcid,
                    ]
                },
            ]
        )
        
        all_subnets = [(s['SubnetId'], s['AvailabilityZone']) for s in response['Subnets']]
    
        # Find AZ -d subnet for ActiveSubnet
        active_subnet, other_subnet = which_subnet_is_az(all_subnets, az_postfix)
        
        vpcid = default_vpcid

    except Exception as e:
        print("There was an error: ", e)
        raise

    # Append values to file
    print(f"{vpcid} {active_subnet} {active_subnet},{other_subnet}")
    if append_parameters_to:
        with open(append_parameters_to, "r") as f:
            yaml_config = yaml.safe_load(f)

        others = {}
        others['vpc_id'] = f"{vpcid}"
        others['active_subnets'] = f"{active_subnet}"
        others['all_subnets'] = f"{active_subnet},{other_subnet}"
        yaml_config['parameters'].update(others)

        with open(append_parameters_to, "w") as f:
            
            #https://github.com/yaml/pyyaml/issues/234
            class IndentDumper(yaml.Dumper):
                def increase_indent(self, flow=False, *args, **kwargs):
                    return super().increase_indent(flow=flow, indentless=False)

            yaml.dump(yaml_config, f, Dumper=IndentDumper)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--region_name', default=None)
    parser.add_argument('--cluster_name', default=None)
    parser.add_argument('--append_parameters_to', default=None)
    parser.add_argument('--az_postfix', default=None)
    parser.add_argument('--profile_name', default='default')
    args = parser.parse_args()

    main(args.region_name, args.profile_name, args.cluster_name, args.append_parameters_to, args.az_postfix)
