#!/usr/bin/env python3

"""
Note:

The OIDC provider should have already been created before this script was ran: 
    eksctl --profile {self.aws_profile} utils associate-iam-oidc-provider --cluster {self.cluster_name} --approve


Usage:
    python3 service_account_role.py --cluster-name opensarlab-test  # defaults: --profile default --sa-namespace jupyter --sa-name hub
    python3 service_account_role.py --cluster-name opensarlab-test -p jupyterhub --sa-namespace jupyter --sa-name=hub 
"""

import argparse
import os
import json

import boto3 
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

def setup_menu():

    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--profile', default='default', help="AWS credential profile")
    parser.add_argument('--sa-namespace', dest='sa_namespace', default='jupyter', help="k8s namespace of service account")
    parser.add_argument('--sa-name', default='hub', dest='sa_name', help="Name of service account")
    parser.add_argument('-c', '--cluster-name', dest='cluster_name', help="Cluster name")

    args = parser.parse_args()

    return args  

class ServiceAccountRole(object):

    def __init__(self, args):
        
        print(f"Args initialized: {args}")

        self.aws_profile = args.profile
        self.sa_namespace = args.sa_namespace 
        self.sa_name = args.sa_name 
        self.cluster_name = args.cluster_name

        # Setup k8s
        try:
            k8s_config.load_kube_config()
        except:
            k8s_config.load_incluster_config()

        self.k8s = k8s_client.CoreV1Api()

        # Setup Boto3
        session = boto3.Session(profile_name=self.aws_profile)
        self.iam = session.client('iam')
        self.sts = session.client('sts')
        self.eks = session.client('eks')

        self.iam_policy_name = f'sa-{self.cluster_name}-{self.sa_namespace}-{self.sa_name}-policy'
        self.iam_role_name = f'sa-{self.cluster_name}-{self.sa_namespace}-{self.sa_name}-role'
        self.inline_policy = None 
        self.iam_role_arn = None

        print(f"IAM policy name: {self.iam_policy_name}")
        print(f"IAM role name: {self.iam_role_name}")

    def _get_aws_account_id(self):
        """
        AWS_ACCOUNT_ID=$(aws --profile ${PROFILE} sts get-caller-identity --query "Account" --output text)
        """
        print("---> Get AWS account id...")
        return self.sts.get_caller_identity().get('Account')

    def _get_oidc_provider(self):
        """
        OIDC_PROVIDER=$(aws --profile ${PROFILE} eks describe-cluster --name ${CLUSTER_NAME} --query "cluster.identity.oidc.issuer" --output text | sed -e "s/^https:\/\///")
        """
        print("---> Get OIDC provider...")
        cluster_info = self.eks.describe_cluster(name=self.cluster_name)
        return cluster_info.get('cluster').get('identity').get('oidc').get('issuer')

    def create_service_account(self):
        """
        kubectl -n ${SERVICE_ACCOUNT_NAMESPACE} create serviceaccount ${SERVICE_ACCOUNT_NAME} --dry-run=client -o yaml | kubectl apply -f -
        """
        print("Create service account...")
        try:
            meta_obj = k8s_client.V1ObjectMeta(name=self.sa_name)
            body = k8s_client.V1ServiceAccount(metadata=meta_obj)
            api_response = self.k8s.create_namespaced_service_account(namespace=self.sa_namespace, body=body)
        except ApiException as e:
            error_body = json.loads(e.body)
            message = error_body['message']
            reason = error_body['reason']

            if reason == 'AlreadyExists':
                print(f"---> {message} for namespace {self.sa_namespace}")
            else:
                raise


    def create_iam_role(self):
        """
        Create IAM role to attach to service account
        https://docs.aws.amazon.com/eks/latest/userguide/create-service-account-iam-policy-and-role.html
        If the cluster was created by eksctl, this would be a one-liner. But, alas, it is not.
        """
        print("Create role...")
        aws_account_id = self._get_aws_account_id()
        oidc_provider = self._get_oidc_provider().replace('https://', '')

        trust_json = f"""
        {{
        "Version": "2012-10-17",
        "Statement": [
            {{
                "Effect": "Allow",
                "Principal": {{
                    "Federated": "arn:aws:iam::{aws_account_id}:oidc-provider/{oidc_provider}"
                }},
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {{
                    "StringEquals": {{
                    "{oidc_provider}:sub": "system:serviceaccount:{self.sa_namespace}:{self.sa_name}"
                    }}
                }}
            }}
        ]
        }}
        """.strip()
        try:
            resp = self.iam.create_role(RoleName=self.iam_role_name, AssumeRolePolicyDocument=trust_json)
        except self.iam.exceptions.EntityAlreadyExistsException as e:
            print("---> Role already exists. skipping....")

        self.iam_role_arn = self.iam.get_role(RoleName=self.iam_role_name).get('Role').get('Arn')
        if not self.iam_role_arn:
            raise Exception(f"Role creation did not work. No ARN exists for {self.iam_role_name}")

    def get_default_inline_policy(self):
        print("Get default inline policy...")
        
        self.inline_policy = """
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "*"
                    ],
                    "Resource": [
                        "*"
                    ]
                }
            ]
        }
        """.strip()

    def add_inline_policy_to_iam_role(self):
        """
        aws --profile ${PROFILE} iam put-role-policy --role-name ${IAM_ROLE_NAME} --policy-name ${IAM_POLICY_NAME} --policy-document file://policy.json
        rm policy.json
        """
        print("Add inline policy to role...")

        response = self.iam.put_role_policy(RoleName=self.iam_role_name, PolicyName=self.iam_policy_name, PolicyDocument=self.inline_policy)


    def associate_iam_role_with_service_account(self):
        """
        kubectl -n ${SERVICE_ACCOUNT_NAMESPACE} annotate sa ${SERVICE_ACCOUNT_NAME} "eks.amazonaws.com/role-arn=${ROLE_ARN}" --dry-run=client -o yaml | kubectl apply -f -
        """
        print(f'Associating role with service account "{self.sa_name}" in "{self.sa_namespace}"')
        body = { 'metadata': { 'annotations': { 'eks.amazonaws.com/role-arn': self.iam_role_arn } } }
        resp = self.k8s.patch_namespaced_service_account(name=self.sa_name, namespace=self.sa_namespace, body=body)

if __name__ == "__main__":

    try:
        args = setup_menu()

        sar = ServiceAccountRole(args)

        sar.create_service_account()
        sar.create_iam_role()
        sar.get_default_inline_policy()
        sar.add_inline_policy_to_iam_role()
        sar.associate_iam_role_with_service_account()

    except Exception as e:
        print("Something went wrong with `service_account_role.py`...")
        raise
