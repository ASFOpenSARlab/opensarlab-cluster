"""
    Cron app that grabs domain whitelists from S3 and applies them to the cluster. 

    Assumes that Istio is installed to current cluster.
"""


import argparse
import logging
import pathlib

logging.basicConfig(format='%(asctime)s %(levelname)s (%(lineno)d) - %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)

from yamllint.config import YamlLintConfig
from yamllint import linter
import boto3
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes import utils
from kubernetes.client.rest import ApiException

import build as build_configs

class BadTimeTagsException(Exception):
    """ If the time tags are bad or in the wrong order """

class SnapshotManagement():

    def __init__(
            self,
            domain_bucket: str,
            cluster_name: str,
            aws_region: str,
            aws_profile: str=None,
            verbose: bool=False, 
            dry_run: bool=False
        ):

        if verbose:
            logging_level = logging.DEBUG
        else:
            logging_level = logging.INFO
        logging.basicConfig(format='%(asctime)s %(levelname)s (%(lineno)d) - %(message)s', level=logging_level)
        self.log = logging.getLogger(__name__)

        if aws_profile:
            session = boto3.Session(region_name=aws_region, profile_name=aws_profile)
        else:
            session = boto3.Session(region_name=aws_region)

        self.domain_bucket = domain_bucket
        self.cluster_name = cluster_name
        self.dry_run = dry_run

        self.log.info(f"""Checking snapshots with
            domain_bucket: '{domain_bucket}',
            cluster_name: '{cluster_name}',
            region: '{aws_region}',
            profile: '{aws_profile}',
            verbose: {verbose},
            dry run: {self.dry_run}
        """)

        self.s3 = session.client('s3')

        try:
            k8s_config.load_incluster_config()
        except:
            k8s_config.load_config()
        self.k8s_api = k8s_client.CoreV1Api()

    def _get_file_folders(self, s3_client, bucket_name, prefix=""):
        file_names = []
        folders = []

        default_kwargs = {
            "Bucket": bucket_name,
            "Prefix": prefix
        }
        next_token = ""

        log.info(f"Getting files from bucket '{bucket_name}' with prefix '{prefix}'.")

        while next_token is not None:
            updated_kwargs = default_kwargs.copy()
            if next_token != "":
                updated_kwargs["ContinuationToken"] = next_token

            response = s3_client.list_objects_v2(**default_kwargs)
            contents = response.get("Contents")

            for result in contents:
                key = result.get("Key")
                if key[-1] == "/":
                    folders.append(key)
                else:
                    file_names.append(key)

            next_token = response.get("NextContinuationToken")

        return file_names, folders


    def _download_files(self, s3_client, bucket_name, local_path, file_names, folders):

        local_path = pathlib.Path(local_path)

        for folder in folders:
            folder_path = pathlib.Path.joinpath(local_path, folder)
            folder_path.mkdir(parents=True, exist_ok=True)

        for file_name in file_names:
            file_path = pathlib.Path.joinpath(local_path, file_name)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            s3_client.download_file(
                bucket_name,
                file_name,
                str(file_path)
            )

    def main(self) -> None:

        try:
            # Make temp folders
            pathlib.Path("/tmp/whitelists/configs/").mkdir(parents=True, exist_ok=True)

            # Download latest whitelist files from S3 to /temp
            file_names, folders = self._get_file_folders(self.s3, self.domain_bucket, prefix=self.cluster_name)
            self._download_files(
                self.s3,
                self.domain_bucket,
                "/tmp/whitelists/configs/",
                file_names,
                folders
            )

            # Parse whitelist configs
            build_configs.main("/tmp/whitelists/configs/", "/app/domain_management/")

            # Lint configs
            ## yamllint -c $HERE/.yamllint $HERE/k8s/egress/
            lint_config = YamlLintConfig(file='/app/domain_management/.yamllint')
            lint_config.validate()
            lint_problems = linter.run('/app/domain_management/egress.yaml', lint_config)
            lint_problems = list(lint_problems)
            if lint_problems:
                raise Exception(f"Problems found in the egress yaml.\n{list(lint_problems)}")

            # Apply egress config
            ## kubectl apply -f $HERE/k8s/egress/egress.yaml
            if self.dry_run:
                log.info("Dry run. Skipping applying of domains to cluster...")
            else:
                log.info("Applying domains to cluster...")
                utils.create_from_yaml(self.k8s_api, '/app/domain_management/egress.yaml', verbose=True)
                pass

        except ApiException as e:
            log.error("Something went wrong with K8s...")
            raise

        self.log.info("Done.")

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Check usage status of snapshots in lab deployment and send emails, remove users as needed.')
    parser.add_argument('--domain-whitelist-bucket', help="Name of S3 bucket containing domain whitelists", dest="domain_bucket", required=True)
    parser.add_argument('--cluster-name', help='K8s cluster name (not short lab name)', dest='cluster_name', required=True)
    parser.add_argument('--region', help='AWS Region name', dest='aws_region', required=True)
    parser.add_argument('--profile', help='AWS profile largely for local development', dest='aws_profile', required=False)
    parser.add_argument('--verbose', help='Show debug messages', dest='verbose', action='store_true', required=False)
    parser.add_argument('--dry-run', help='Dry run email, removal, and deletions.', dest='dry_run', action='store_true', required=False)
    args = vars(parser.parse_args())

    vm = SnapshotManagement(**args)
    vm.main()
