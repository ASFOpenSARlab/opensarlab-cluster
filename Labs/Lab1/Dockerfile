FROM jupyter/minimal-notebook:83ed2c63671f
LABEL MAINTAINER="Alaska Satellite Facility"

# By default, the notebook base image is set to non-sudo user joyvan. This makes root-ful actions difficult.
USER root

RUN apt-get update && \
    apt-get install --no-install-recommends -y software-properties-common && \
    add-apt-repository -y ppa:ubuntugis/ubuntugis-unstable
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    python \
    python-pip \
    gdal-bin \
    libgsl-dev \
    zip \
    wget \
    python-gdal \
    awscli \
    shapelib \
    groff \
    vim \
    && rm -rf /var/lib/apt/lists/*

RUN pip install 'boto3>=1.4.4' 'psycopg2>=2.7.1' 'pyyaml>=3.12' 'lxml>=3.8.0' 'numpy>=1.13.0' 'pandas==0.23.0'

#COPY ASF_MapReady_CLI.tar.gz /tmp/ASF_MapReady.tar.gz
#RUN cd /tmp/ && tar xzvf ASF_MapReady.tar.gz && cd ASF_MapReady && make install && rm -rf /tmp/ASF_MapReady*

#COPY src /usr/local/sbin
#COPY config /usr/local/config

# Copy aws config for locked-down user. Secret keys will be via the helm config
#COPY .aws/ /home/commons/.aws/
RUN cp -r /home/jovyan/. /home/commons/

ARG buildtag
RUN echo $buildtag > /home/commons/.build_tag

RUN chown -R jovyan:root /home/commons/

USER jovyan
