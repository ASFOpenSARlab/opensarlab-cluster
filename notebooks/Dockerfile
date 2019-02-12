FROM jupyter/minimal-notebook:83ed2c63671f
LABEL MAINTAINER="Alaska Satellite Facility"

# By default, the notebook base image is set to non-sudo user joyvan. This makes root-ful actions difficult.
USER root

RUN apt-get update && \
    apt-get install --no-install-recommends -y software-properties-common && \
    add-apt-repository -y ppa:ubuntugis/ubuntugis-unstable
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    python3 \
    python3-pip \
    gdal-bin \
    libgsl-dev \
    zip \
    wget \
    python3-gdal \
    awscli \
    shapelib \
    groff \
    vim

# Some libraries for MapReady
RUN apt-get install --no-install-recommends -y \
    pkg-config \
    libxml2-dev \
    libgsl-dev \
    libpng-dev \
    bison \
    flex \
    gcc \
    libtiff-dev \
    libgeotiff-dev \
    libhdf5-dev \
    libglib2.0-dev \
    libgdal-dev \
    libshp-dev

RUN rm -rf /var/lib/apt/lists/*

RUN pip3 install 'boto3>=1.4.4' 'psycopg2>=2.7.1' 'pyyaml>=3.12' 'lxml>=3.8.0' 'numpy>=1.13.0' 'pandas==0.23.0'

# Install MapReady
COPY software/ASF_MapReady_CLI.tar.gz /tmp/ASF_MapReady.tar.gz
RUN cd /tmp/ && tar xzvf ASF_MapReady.tar.gz && cd ASF_MapReady && make install && rm -rf /tmp/ASF_MapReady*

# It's assumed that the compiled versions of previous libaries will have the same behavior
RUN cp /usr/lib/x86_64-linux-gnu/libgsl.so /usr/lib/x86_64-linux-gnu/libgsl.so.19
RUN cp /usr/lib/x86_64-linux-gnu/libproj.so /usr/lib/x86_64-linux-gnu/libproj.so.9
RUN cp /usr/lib/x86_64-linux-gnu/libhdf5_serial.so /usr/lib/x86_64-linux-gnu/libhdf5_serial.so.10
RUN cp /usr/lib/x86_64-linux-gnu/libnetcdf.so /usr/lib/x86_64-linux-gnu/libnetcdf.so.11

RUN wget -q -O /tmp/libpng12.deb http://mirrors.kernel.org/ubuntu/pool/main/libp/libpng/libpng12-0_1.2.54-1ubuntu1_amd64.deb \
    && dpkg -i /tmp/libpng12.deb \
    && rm /tmp/libpng12.deb


# Install ISCE
ENV ISCE_HOME /usr/local/isce
ENV PATH $PATH:$ISCE_HOME/bin:$ISCE_HOME/applications
ENV PYTHONPATH $PYTHONPATH:/usr/local/

COPY software/ice.tar.bz2 /tmp/ice.tar.bz2
RUN cd /tmp/ && tar -xjf ice.tar.bz2 && mv isce-20160906 $ISCE_HOME


# Copy aws config for locked-down user. Secret keys will be via the helm config
RUN cp -r /home/jovyan/. /home/commons/

RUN chown -R jovyan:root /home/commons/

#USER jovyan
