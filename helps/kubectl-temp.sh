#!/bin/bash

#
# In order to locally manage a remote EKS cluster, a K8s config must be configured properly.
# This script makes the configuring simpler. 
# You need to rerun after the AWS session expires (about every hour)
# Usage: kubectl-temp.sh {cluster-name}
#
# Users will need to be added as Trusted to the cluster access ROLE for this to work.
# For ease, an alias works well: alias sk=/path/kubectl-temp.sh
#
# The local AWS config file is required to include certain things:
#
#   [profile THIS_CAN_BE_ANY_NAME]
#   region = MY_AWS_REGION
#   role_arn = THE_ARN_OF_THE_CLUSTER_ACCESS_ROLE
#   cluster_name = THE_NAME_OF_THE_EKS_CLUSTER
#

AWS_PROFILE=$1
CLUSTER_NAME=$(aws configure get cluster_name --profile=$AWS_PROFILE)
CLUSTER_NAMESPACE=jupyter

if [[ $# -eq 0 ]]
then
    aws configure list-profiles
    exit 0
fi

echo "Using \"$CLUSTER_NAME\" with namespace \"$CLUSTER_NAMESPACE\" by AWS config profile \"$AWS_PROFILE\""

rm ~/.kube/config || true
aws --profile=$AWS_PROFILE eks update-kubeconfig --name $CLUSTER_NAME

# Set namespace to default to jupyter
kubectl config set-context --current --namespace=$CLUSTER_NAMESPACE
