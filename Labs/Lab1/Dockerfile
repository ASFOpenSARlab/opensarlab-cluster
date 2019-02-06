FROM jupyter/minimal-notebook:83ed2c63671f
LABEL MAINTAINER="Alaska Satellite Facility"

ENV MAPREADY_VERSION=ASF_MapReady

# By default, the notebook base image is set to non-sudo user joyvan. This makes root-ful actions difficult.
USER root

RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:ubuntugis/ubuntugis-unstable
RUN apt-get update && \
    apt-get install -y \
    python \
    python-pip \
    gdal-bin \
    libgsl-dev \
    zip \
    wget \
    python-gdal \
    awscli \
    shapelib

RUN pip install 'boto3>=1.4.4' 'psycopg2>=2.7.1' 'pyyaml>=3.12' 'lxml>=3.8.0' 'numpy>=1.13.0'

COPY ${MAPREADY_VERSION}.tar.gz /tmp/
RUN cd /tmp/ && tar xzvf ${MAPREADY_VERSION}.tar.gz && cd ${MAPREADY_VERSION} && make install && rm -rf /tmp/${MAPREADY_VERSION}*

#COPY src /usr/local/sbin
#COPY config /usr/local/config

#USER jovyan

#ENTRYPOINT ["/usr/bin/python", "/usr/local/sbin/daemon.py"]
