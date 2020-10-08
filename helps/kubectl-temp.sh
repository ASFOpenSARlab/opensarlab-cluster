# You need to run against the root account and not a sub-account. That's what the STS part does.
# Users will need to be added as Trusted to the _jupyter-hub-build_ role for this to work.
# For ease, an alias works well: alias sk=/path/kubectl-temp.sh

AWS_PROFILE=jupyterhub
AWS_REGION=us-east-1
AWS_CLUSTER_ROLE=arn:aws:iam::553778890976:role/jupyter-hub-build
CLUSTER_NAME=$1
CLUSTER_NAMESPACE=jupyter

STS_DICT=$(aws sts assume-role --role-arn $AWS_CLUSTER_ROLE --role-session-name ARandomSessionNameYouPickHere --profile=$AWS_REGION)

export AWS_ACCESS_KEY_ID=$(python -c "print($STS_DICT['Credentials']['AccessKeyId'])")
export AWS_SECRET_ACCESS_KEY=$(python -c "print($STS_DICT['Credentials']['SecretAccessKey'])")
export AWS_SESSION_TOKEN=$(python -c "print($STS_DICT['Credentials']['SessionToken'])")

rm ~/.kube/config
aws eks update-kubeconfig --name $CLUSTER_NAME --region=$AWS_REGION --profile=$AWS_PROFILE

# Set namespace to default to jupyter
kubectl config set-context --current --namespace=$CLUSTER_NAMESPACE
