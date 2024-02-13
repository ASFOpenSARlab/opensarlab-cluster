
import argparse

import yaml
import boto3

from utils.custom_yaml import IndentDumper

def main(config, aws_region, aws_profile):
    with open(config, "r") as infile:
        yaml_config = yaml.safe_load(infile)

    lab_domain = str(yaml_config['parameters']['lab_domain']).strip().lower()
    print(f"lab domain in opensciencelab.yaml is '{lab_domain}'")

    if lab_domain == 'load balancer':
        
        cost_tag_value = yaml_config['parameters']['cost_tag_value']
        lb_name = f"{cost_tag_value}"

        session = None 
        try:
            session = boto3.Session(region_name=aws_region, profile_name=aws_profile)
        except:
            session = boto3.Session(region_name=aws_region)
        lb = session.client('elbv2')

        response = lb.describe_load_balancers(
                Names=[
                    str(lb_name),
                ]
            )

        lab_domain = f"https://{response['LoadBalancers'][0]['DNSName']}"

        print(f"lab domain is now {lab_domain}")

        others = {}
        others['lab_domain'] = f"{lab_domain}"
        yaml_config['parameters'].update(others)

        with open(config, "w") as f:
            yaml.dump(yaml_config, f, Dumper=IndentDumper)

    else:
        if 'http://' in lab_domain:
            raise Exception("http is not valid in lab domain. Please fix.")
        elif 'https://' not in lab_domain:
            print(f"https is required in lab domain. Prepending to {lab_domain}")
            lab_domain = f"https://{lab_domain}"


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    parser.add_argument('--aws_region', default=None)
    parser.add_argument('--aws_profile', default=None)
    args = parser.parse_args()

    main(args.config, args.aws_region, args.aws_profile)