#!/bin/bash

BASE_REPO_NAME=asf-franz-labs
BASE_IMAGE=553778890976.dkr.ecr.us-east-1.amazonaws.com/$BASE_REPO_NAME
BASE_TAG=$2

if [[ $1 == '--build' && $2 == '' ]]; then
    echo "Building needs a build tag"

elif [[ $1 == '--build' && $2 != '' ]]; then
    echo "Building $BASE_IMAGE:$BASE_TAG"
    docker build -t $BASE_IMAGE:$BASE_TAG -f Dockerfile --squash .

elif [[ $1 == '--push' && $2 == '' ]]; then
    echo "Pushing needs a build tag"

elif [[ $1 == '--push' && $2 != '' ]]; then
    echo "Pushing $BASE_IMAGE:$BASE_TAG"
    $(aws ecr get-login --no-include-email --profile jupyterhub)
    docker push $BASE_IMAGE:$BASE_TAG

elif [[ $1 == '--list' ]]; then
    echo "Grabbing current images stored in ECR"
    aws ecr list-images --repository-name $BASE_REPO_NAME
fi