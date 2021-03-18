#!/bin/bash

#
# In order to locally manage a remote EKS cluster, a K8s config must be configured properly.
# This script makes the configuring simpler. 
# You need to rerun after the AWS session expires (about every hour)
# Usage: kubectl-temp.sh {cluster-name}
#
# Users will need to be added as Trusted to the _opensarlab-test-build_ (or equivalent) role for this to work.
# For ease, an alias works well: alias sk=/path/kubectl-temp.sh
#

CLUSTER_NAME=$1
CLUSTER_NAMESPACE=jupyter
AWS_PROFILE=$CLUSTER_NAME-access

rm ~/.kube/config
aws eks update-kubeconfig --name $CLUSTER_NAME --profile=$AWS_PROFILE

# Set namespace to default to jupyter
kubectl config set-context --current --namespace=$CLUSTER_NAMESPACE
