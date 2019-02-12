#! /bin/bash

aws s3 sync --exclude '*' --include 'ASF_MapReady_CLI.tar.gz' s3://hyp3-docker/software/ . --profile=hyp3

aws s3 sync --exclude '*' --include 'ice.tar.bz2' s3://grfn-software/ . --profile=grfn
