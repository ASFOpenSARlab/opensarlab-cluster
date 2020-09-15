#!/bin/bash

# These are a set of AWS commands that build out resouces outside Cloudformation
# These are meant to be created once and do not need to be overriden (accidently or otherwise) on subsequent builds.
# Most of these are required, though may be removed if no longer used
# The following assume that the AWS account has been created and the local AWS config file is configured properly

if [[ "$#" == 0 ]] ; then
   PROFILE=default
elif [[ "$#" == 1 ]] ; then
   PROFILE=$1
fi

echo "Using AWS profile '$PROFILE'"

#### User Params
MY_DOCKER_HUB_CREDS=asfdaac:myPassword


#### Roles 

#### Cognito 

#### Secret Manager
echo "Creating Docker Hub secret entry. Password needs to be updated manually..."
# Create secret for Docker Hub user to be used in image pulls
# To retrieve: aws --profile=$PROFILE secretsmanager get-secret-value --secret-id dockerhub/creds --version-stage AWSCURRENT
aws --profile=$PROFILE secretsmanager create-secret --name dockerhub/creds --description "Docker Hub Username/Password" --secret-string $MY_DOCKER_HUB_CREDS
