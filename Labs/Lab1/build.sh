#!/bin/bash

BASE_IMAGE=553778890976.dkr.ecr.us-east-1.amazonaws.com/asf-franz-labs
BASE_TAG=build.7

#aws s3 sync --exclude '*' --include 'ASF_MapReady_CLI.tar.gz' s3://hyp3-docker/software/ .

docker build -t $BASE_IMAGE:$BASE_TAG -f Dockerfile --squash --build-arg buildtag=$BASE_TAG .
#$(aws ecr get-login --no-include-email --profile jupyterhub)
#docker push $BASE_IMAGE:$BASE_TAG
