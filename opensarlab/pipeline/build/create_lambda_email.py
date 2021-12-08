import pathlib
import argparse
from zipfile import ZipFile
import uuid

import boto3
import yaml
from jinja2 import Environment, FileSystemLoader

from utils.custom_yaml import IndentDumper

def main(config, aws_region, template_path, s3_bucket_name, aws_profile_name):

    template_path = pathlib.Path(template_path)

    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        autoescape=True
    )

    with open(config, "r") as infile:
        yaml_config = yaml.safe_load(infile)

    admin_email_address = yaml_config['parameters']['admin_email_address']
    deployment_url = yaml_config['parameters']['deployment_url']
    user_whitelist_csv = yaml_config['parameters'].get('user_whitelist_csv', None)
    user_whitelist_bucket = yaml_config['parameters'].get('user_whitelist_bucket', None)

    # Render lambda_email_py template
    template = env.get_template(template_path.name)

    lambda_email_base = f"lambda_email_zip_{str(uuid.uuid4())[:8]}"
    lambda_email_py = f"{lambda_email_base}.py"
    lambda_email_zip = f"{lambda_email_base}.py.zip"

    with open(lambda_email_py, 'w') as outfile:
        outfile.write(template.render(
            aws_region=aws_region, 
            admin_email_address=admin_email_address, 
            deployment_url=deployment_url,
            user_whitelist_bucket = user_whitelist_bucket,
            user_whitelist_csv = user_whitelist_csv
            )
        )

    # Zip lambda_email.py
    with ZipFile(lambda_email_zip,'w') as zip:
        zip.write(lambda_email_py)

    # Upload lamda_email.py* to S3
    session = None 
    try:
        session = boto3.Session(region_name=aws_region, profile_name=aws_profile_name)
    except:
        session = boto3.Session(region_name=aws_region)
    s3 = session.client('s3')

    try:
        s3.create_bucket(
            Bucket=s3_bucket_name,
            CreateBucketConfiguration={
                'LocationConstraint': f"{aws_region}"
            },
        )
    except s3.exceptions.BucketAlreadyExists as e:
        print(f"Bucket {e.response['Error']['BucketName']} already exists.")

    except s3.exceptions.BucketAlreadyOwnedByYou as e:
        print(f"Bucket {e.response['Error']['BucketName']} is already owned by you.")

    s3.upload_file(lambda_email_zip, s3_bucket_name, lambda_email_zip)
    s3.upload_file(lambda_email_py, s3_bucket_name, lambda_email_py)

    # Update parameter in config
    print(f"The lambda email zip file is now {lambda_email_zip}. Adding to parameters...")

    # Update config to reflect lambda_email.zip* version
    others = {}
    others['lambda_email_zip'] = f"{lambda_email_zip}"
    others['lambda_email_base'] = f"{lambda_email_base}"
    yaml_config['parameters'].update(others)

    with open(config, "w") as f:
        yaml.dump(yaml_config, f, Dumper=IndentDumper)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    parser.add_argument('--aws_region', default=None)
    parser.add_argument('--s3_bucket_name', default=None)
    parser.add_argument('--aws_profile_name', default=None)
    parser.add_argument('--template_path', default=None)
    args = parser.parse_args()

    main(args.config, args.aws_region, args.template_path, args.s3_bucket_name, args.aws_profile_name)
