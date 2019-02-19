#!/bin/bash

BASE_IMAGE=553778890976.dkr.ecr.us-east-1.amazonaws.com/asf-franz-labs
BASE_TAG=build.13

docker build -t $BASE_IMAGE:$BASE_TAG -f Dockerfile --squash .

#$(aws ecr get-login --no-include-email --profile jupyterhub)
#docker push $BASE_IMAGE:$BASE_TAG
