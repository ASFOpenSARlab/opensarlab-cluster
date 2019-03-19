#! /bin/bash

# Unzip all zips and tars so that we are only importing into the dockerfile plain files. This will make any future migration easier.

echo "Downloading GIAnT...."
if [ ! -d GIAnT ] ; then
    aws s3 sync --exclude '*' --include 'GIAnT.zip' s3://asf-jupyter-software/ . --profile=jupyterhub
    unzip GIAnT.zip
fi

echo "Downloading MapReady..."
if [ ! -d ASF_MapReady ] ; then
    aws s3 sync --exclude '*' --include 'ASF_MapReady_CLI.tar.gz' s3://asf-jupyter-software/ . --profile=jupyterhub
    tar xzvf ASF_MapReady_cli.tar.gz
fi

echo "Downloading isce...."
if [ ! -d isce ] ; then
    aws s3 sync --exclude '*' --include 'isce.zip' s3://asf-jupyter-software/ . --profile=jupyterhub
    unzip isce.zip
fi

echo "Downloading snap..."
aws s3 sync --exclude '*' --include 'esa-snap_sentinel_unix_5_0.sh' s3://asf-jupyter-software/ . --profile=jupyterhub

echo "Downloading other files...."
aws s3 sync --exclude '*' --include 'focus.py' s3://asf-jupyter-software/ . --profile=jupyterhub

aws s3 sync --exclude '*' --include 'prepdataxml.py' s3://asf-jupyter-software/ . --profile=jupyterhub

aws s3 sync --exclude '*' --include 'topo.py' s3://asf-jupyter-software/ . --profile=jupyterhub

aws s3 sync --exclude '*' --include 'unpackFrame_ALOS_raw.py' s3://asf-jupyter-software/ . --profile=jupyterhub

aws s3 sync --exclude '*' --include 'snap_install.varfile' s3://asf-jupyter-software/ . --profile=jupyterhub

aws s3 sync --exclude '*' --include 'gpt.vmoptions' s3://asf-jupyter-software/ . --profile=jupyterhub
