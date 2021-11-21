
import argparse

import yaml
import boto3

from opensarlab.utils.custom_yaml import IndentDumper

def main(config, aws_region, aws_profile):
    with open(config, "r") as infile:
        yaml_config = yaml.safe_load(infile)

    deployment_url = str(yaml_config['parameters']['deployment_url']).strip().lower()
    print(f"Deployment url in opensarlab.yaml is '{deployment_url}'")

    if deployment_url == 'load balancer':
        
        cost_tag_value = yaml_config['parameters']['cost_tag_value']
        lb_name = f"{cost_tag_value}"

        session = None 
        try:
            session = boto3.session.Session(region_name=aws_region, profile_name=aws_profile)
        except:
            session = boto3.session.Session(region_name=aws_region)
        lb = session.client('elbv2')

        response = lb.describe_load_balancers(
                Names=[
                    str(lb_name),
                ]
            )

        deployment_url = f"https://{response['LoadBalancers'][0]['DNSName']}"

        print(f"Deployment url is now {deployment_url}")

        others = {}
        others['deployment_url'] = f"{deployment_url}"
        yaml_config['parameters'].update(others)

        with open(config, "w") as f:
            yaml.dump(yaml_config, f, Dumper=IndentDumper)

    else:
        if 'http://' in deployment_url:
            raise Exception("http is not valid in deployment url. Please fix.")
        elif 'https://' not in deployment_url:
            print(f"https is required in deployment url. Prepending to {deployment_url}")
            deployment_url = f"https://{deployment_url}"


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    parser.add_argument('--aws_region', default=None)
    parser.add_argument('--aws_profile', default=None)
    args = parser.parse_args()

    main(args.config, args.aws_region, args.aws_profile)
