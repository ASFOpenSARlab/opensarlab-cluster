#!/bin/bash

#
# In order to locally manage a remote EKS cluster, a K8s config must be configured properly.
# This script makes the configuring simpler. 
# You need to rerun after the AWS session expires (hourly)
# Usage: kubectl-temp.sh {cluster-name}
#
# Users will need to be added as Trusted to the <deployment_name>-cluster-access role for this to work.
# Example trust relationship json:
# {
#  "Version": "2008-10-17",
#  "Statement": [
#    {
#      "Effect": "Allow",
#      "Principal": {
#        "AWS": [
#          "arn:aws:iam::<account_#>:user/<username>",
#        ]
#      },
#      "Action": "sts:AssumeRole"
#    }
#  ]
# }
#
#
# For ease, an alias works well: alias sk=/path/kubectl-temp.sh
#

CLUSTER_NAME=$1
CLUSTER_NAMESPACE=jupyter
AWS_PROFILE=$CLUSTER_NAME-access

rm ~/.kube/config
aws eks update-kubeconfig --name $CLUSTER_NAME --profile=$AWS_PROFILE

# Set namespace to default to jupyter
kubectl config set-context --current --namespace=$CLUSTER_NAMESPACE
