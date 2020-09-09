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
        #os.environ['KUBERNETES_SERVICE_PORT'] = meta['kubernetes_service_port']
        #os.environ['KUBERNETES_SERVICE_HOST'] = meta['kubernetes_service_host']
        #k8s_config.load_incluster_config()
        k8s_config.load_kube_config()
        self.k8s = k8s_client.CoreV1Api()

        # Setup Boto3
        session = boto3.Session()
        self.iam = session.client('iam')

        self.iam_policy_name = f'sa-{self.cluster_name}-{self.sa_namespace}-{self.sa_name}-policy'
        self.iam_policy_name = f'sa-{self.cluster_name}-{self.sa_namespace}-{self.sa_name}-role'

    def create_service_account(self):
        """
        kubectl -n ${SERVICE_ACCOUNT_NAMESPACE} create serviceaccount ${SERVICE_ACCOUNT_NAME} --dry-run=client -o yaml | kubectl apply -f -
        """
        try:
            meta_obj = k8s_client.V1ObjectMeta(name=self.sa_name)
            body = k8s_client.V1ServiceAccount(metadata=meta_obj)
            api_response = self.k8s.create_namespaced_service_account(namespace=self.sa_namespace, body=body)
        except ApiException as e:
            # TODO: Parse e for response code
            #if (e.body)[0]['code'] == 409:
            #    print(f"Service Account named {self.sa_namespace}:{self.sa_name} creation conflict. {(e.body)[0]['message']}. Skipping to next step...")
            #else:
            #    raise
            pass

    def create_iam_role(self):
        """
        # Create IAM role to attach to service account
        # # Create IAM role to attach to service account
        # https://docs.aws.amazon.com/eks/latest/userguide/create-service-account-iam-policy-and-role.html
        # If the cluster was created by eksctl, this would be a one-liner. But, alas, it is not.
        echo "Create role..."
        AWS_ACCOUNT_ID=$(aws --profile ${PROFILE} sts get-caller-identity --query "Account" --output text)
        OIDC_PROVIDER=$(aws --profile ${PROFILE} eks describe-cluster --name ${CLUSTER_NAME} --query "cluster.identity.oidc.issuer" --output text | sed -e "s/^https:\/\///")

        cat << EOF > trust.json
        {
        "Version": "2012-10-17",
        "Statement": [
            {
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/${OIDC_PROVIDER}"
            },
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringEquals": {
                "${OIDC_PROVIDER}:sub": "system:serviceaccount:${SERVICE_ACCOUNT_NAMESPACE}:${SERVICE_ACCOUNT_NAME}"
                }
            }
            }
        ]
        }
        EOF 
        """

    def create_inline_policy(self):
        """
        echo "Create role policy..." 
        cat << EOF > policy.json
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
        EOF
        """

    def add_inline_policy_to_iam_role(self):
        """
        aws --profile ${PROFILE} iam put-role-policy --role-name ${IAM_ROLE_NAME} --policy-name ${IAM_POLICY_NAME} --policy-document file://policy.json
        rm policy.json
        """

    def associate_iam_role_with_service_account(self):
        """
        kubectl -n ${SERVICE_ACCOUNT_NAMESPACE} annotate sa ${SERVICE_ACCOUNT_NAME} "eks.amazonaws.com/role-arn=${ROLE_ARN}" --dry-run=client -o yaml | kubectl apply -f -
        """

if __name__ == "__main__":

    args = setup_menu()

    sar = ServiceAccountRole(args)

    sar.create_service_account()
    sar.create_iam_role()
    sar.create_inline_policy()
    sar.add_inline_policy_to_iam_role()
    sar.associate_iam_role_with_service_account()
