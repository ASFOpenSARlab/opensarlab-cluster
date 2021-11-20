
import argparse

import yaml
import boto3

from opensarlab.utils.custom_yaml import IndentDumper

def main(config, aws_region, aws_profile):
    with open(config, "r") as infile:
        yaml_config = yaml.safe_load(infile)

    deployment_url = str(yaml_config['parameters']['deployment_url']).trim().lower()
    print(f"Deployment url in opensarlab.yaml is '{deployment_url}'")

    if deployment_url == 'load balancer':
        
        cost_tag_value = yaml_config['parameters']['cost_tag_value']
        lb_name = f"{aws_region}-{cost_tag_value}-cluster-lb"

        session = None 
        try:
            session = boto3.session.Session(aws_region=aws_region, aws_profile=aws_profile)
        except:
            session = boto3.session.Session(aws_region=aws_region)
        lb = session.client('elbv2')

        response = lb.describe_load_balancers(
                Names=[
                    str(lb_name),
                ]
            )

        deployment_url = response['LoadBalancers'][0]['DNSName']
        print(f"Deployment url is now {deployment_url}")

        others = {}
        others['deployment_url'] = f"{deployment_url}"
        yaml_config['parameters'].update(others)

        with open(config, "w") as f:
            yaml.dump(yaml_config, f, Dumper=IndentDumper)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    parser.add_argument('--aws_region', default=None)
    parser.add_argument('--aws_profile', default=None)
    args = parser.parse_args()

    main(args.config, args.aws_region, args.aws_profile)
