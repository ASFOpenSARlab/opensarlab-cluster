#!/bin/bash

BASE_IMAGE=docker-registry.asf.alaska.edu:5000/asf-franz-labs

# Lab 1
docker build -t $BASE_IMAGE:Lab_1 -f Lab1/Dockerfile Lab1/.
# docker push $BASE_IMAGE:Lab_1
