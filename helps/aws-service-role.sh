#!/bin/bash

#
# The following assumes that local AWS credential profiles have already been made and the local kubeconfig is properly set.
#
# The following is used to apply K8s Service Accounts with IAM roles to the cluster. 
# A close variation of this is used within helm_config.yaml.
# This script is used more for informational purposes.
#
#
####  Some parameters
#
#  bash aws-service-role.sh {cluster name} {service account namespace} {service account name} {optional awscli profile name}
#
#

set -ex

if [[ "$#" == 3 ]] ; then
   PROFILE=default
elif [[ "$#" == 4 ]] ; then
   PROFILE=$4
fi

echo "Using AWS profile '$PROFILE'"

CLUSTER_NAME=$1
SERVICE_ACCOUNT_NAMESPACE=$2
SERVICE_ACCOUNT_NAME=$3

IAM_POLICY_NAME=SA-${CLUSTER_NAME}-${SERVICE_ACCOUNT_NAMESPACE}-${SERVICE_ACCOUNT_NAME}-POLICY
IAM_ROLE_NAME=SA-${CLUSTER_NAME}-${SERVICE_ACCOUNT_NAMESPACE}-${SERVICE_ACCOUNT_NAME}-ROLE

#### 

# Install eksctl to make some things much easier. Uncomment if needed.
#echo "Installing eksctl..."
#curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
#sudo mv /tmp/eksctl /usr/local/bin
#eksctl version

# Create service account
echo "Create service account..."
kubectl -n ${SERVICE_ACCOUNT_NAMESPACE} create serviceaccount ${SERVICE_ACCOUNT_NAME} --dry-run=client -o yaml | kubectl apply -f -

# Create oidc-provider
echo "Create oidc provider..."
eksctl --profile ${PROFILE} utils associate-iam-oidc-provider --cluster ${CLUSTER_NAME} --approve

# Create IAM role to attach to service account
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

aws --profile ${PROFILE} iam get-role --role-name ${IAM_ROLE_NAME} 
aws --profile ${PROFILE} iam create-role --role-name ${IAM_ROLE_NAME} --assume-role-policy-document file://trust.json --description "" || \
    aws --profile ${PROFILE} iam update-role --role-name ${IAM_ROLE_NAME} --assume-role-policy-document file://trust.json --description ""
rm trust.json
ROLE_ARN="$(aws --profile ${PROFILE} iam get-role --role-name ${IAM_ROLE_NAME} --query "Role.Arn" --output text)"
echo "Role ARN: ${ROLE_ARN}"

# Create policy
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

# Add inline policy to role. Put does both create and update
aws --profile ${PROFILE} iam put-role-policy --role-name ${IAM_ROLE_NAME} --policy-name ${IAM_POLICY_NAME} --policy-document file://policy.json
rm policy.json

# Associalte role with service account
echo "Associate role with service account..."
kubectl -n ${SERVICE_ACCOUNT_NAMESPACE} annotate sa ${SERVICE_ACCOUNT_NAME} "eks.amazonaws.com/role-arn=${ROLE_ARN}" --dry-run=client -o yaml | kubectl apply -f -

# Respawn pod for changes to take affect
# Assumes that the pod namespace is the same as the service account ns
echo "Respawn hub pod..."
kubectl -n ${SERVICE_ACCOUNT_NAMESPACE} delete pod -l component=hub
