

import argparse

import boto3

"""
    python3 get_vpcid_and_subnets.py --region_name=${AWS::Region} --cluster_name=${AWS::StackName}
"""

def which_subnet_is_d(subnets, az_postfix):
    
    for subid, az in subnets:
        if az_postfix in az:
            active_subnet = subid
        else:
            other_subnet = subid
    
    return active_subnet, other_subnet

def main(region_name, profile_name, cluster_name, append_parameters, az_postfix):

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
        active_subnet, other_subnet = which_subnet_is_d(all_subnets, az_postfix)
        
    except Exception as e:
        
        print("There was an error: ", e)
        
        # Create new non-default VPC. This will auto-include subnets
        #response = client.create_vpc(
        #    CidrBlock='string', 
        #    DryRun=True
        #)
        #print(response)
        
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
        active_subnet, other_subnet = which_subnet_is_d(all_subnets)
        
        vpcid = default_vpcid

    # Append values to file
    print(f"{vpcid} {active_subnet} {active_subnet},{other_subnet}")
    if append_parameters:
        with open(append_parameters, 'a') as f:
            f.write(
        f"""

others:
    vpc_id: {vpcid}
    active_subnets: {active_subnet}
    all_subnets: {active_subnet},{other_subnet}
""")

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--region_name', default=None)
    parser.add_argument('--cluster_name', default=None)
    parser.add_argument('--append_parameters', default=None)
    parser.add_argument('--az_postfix', default=None)
    parser.add_argument('--profile_name', default='default')
    args = parser.parse_args()

    main(args.region_name, args.profile_name, args.cluster_name, args.append_parameters, args.az_postfix)
