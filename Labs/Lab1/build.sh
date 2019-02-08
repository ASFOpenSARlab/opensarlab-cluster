#!/bin/bash

BASE_IMAGE=docker-registry.asf.alaska.edu:5000/asf-franz-labs

#aws s3 sync --exclude '*' --include 'ASF_MapReady_CLI.tar.gz' s3://hyp3-docker/software/ .

docker build -t $BASE_IMAGE:Base -f Dockerfile --squash .
#docker push $BASE_IMAGE:Base

#docker run -it $BASE_IMAGE:Lab1 bash
