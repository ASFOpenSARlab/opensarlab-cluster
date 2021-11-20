import pathlib
import argparse

import boto3
import yaml
from jinja2 import Environment, FileSystemLoader

from opensarlab.utils.custom_filters import regex_replace

env = Environment(
    loader=FileSystemLoader(pathlib.Path(__file__).parent),
    autoescape=True
)

env.filters['regex_replace'] = regex_replace

def main(config, aws_region, aws_profile_name):
    with open(config, "r") as infile:
        yaml_config = yaml.safe_load(infile)

    admin_email_address = yaml_config['admin_email_address']
    deployment_url = yaml_config['deployment_url']
    cost_tag_value = yaml_config['cost_tag_value']

    template = env.get_template('templates/lambda.py.jinja')

    with open('lambda_handler.py', 'w') as outfile:
        outfile.write(template.render(
            aws_region=aws_region, 
            admin_email_address=admin_email_address, 
            deployment_url=deployment_url
            )
        )

    session = None 
    try:
        session = boto3.session.Session(region_name=aws_region, profile_name=aws_profile_name)
    except:
        session = boto3.session.Session(region_name=aws_region)
    s3 = session.client('s3')

    s3_bucket_name = f"{aws_region}-{cost_tag_value}-lambda"

    try:
        s3.create_bucket(Bucket=s3_bucket_name)
    except s3.meta.client.exceptions.BucketAlreadyExists as e:
        print(f"Bucket {e.response['Error']['BucketName']} already exists.")

    s3.meta.client.upload_file('lambda_handler.py', s3_bucket_name, 'lambda_handler.py')

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    parser.add_argument('--aws_region', default=None)
    parser.add_argument('--s3_bucket_name', default=None)
    parser.add_argument('--aws_profile_name', default=None)
    args = parser.parse_args()

    main(args.config, args.aws_region, args.s3_bucket_name, args.aws_profile_name)