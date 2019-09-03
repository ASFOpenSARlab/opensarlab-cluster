# You need to run against the root account and not a sub-account
# Users will need to be added as Trusted to the _jupyter-hub-build_ role for this to work.

AWS_REGION=us-east-1
STS_DICT=$(aws sts assume-role --role-arn arn:aws:iam::553778890976:role/jupyter-hub-build --role-session-name ARandomSessionNameYouPickHere --profile=$AWS_REGION)

export AWS_ACCESS_KEY_ID=$(python -c "print($STS_DICT['Credentials']['AccessKeyId'])")
export AWS_SECRET_ACCESS_KEY=$(python -c "print($STS_DICT['Credentials']['SecretAccessKey'])")
export AWS_SESSION_TOKEN=$(python -c "print($STS_DICT['Credentials']['SessionToken'])")

rm ~/.kube/config
aws eks update-kubeconfig --name $1 --region=$AWS_REGION --profile=jupyterhub

# Set namespace to default to jupyter
kubectl config set-context --current --namespace=jupyter
