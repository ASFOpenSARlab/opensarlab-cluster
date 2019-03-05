FROM jupyter/minimal-notebook:83ed2c63671f
LABEL MAINTAINER="Alaska Satellite Facility"

# By default, the notebook base image is set to non-sudo user joyvan. This makes root-ful actions difficult.
USER root

RUN apt update && \
    apt install --no-install-recommends -y software-properties-common && \
    add-apt-repository -y ppa:ubuntugis/ubuntugis-unstable
RUN apt update \
    && apt install --no-install-recommends -y \
    python3.6 \
    python3-pip \
    python2.7 \
    python-pip \
    gfortran \
    python-gdal \
    gdal-bin \
    libgsl-dev \
    zip \
    wget \
    python3-gdal \
    awscli \
    shapelib \
    groff \
    vim \
    python3-setuptools \
    rsync

# Some libraries for MapReady
RUN apt install --no-install-recommends -y \
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

# Some libaries for ISCE
RUN apt install --no-install-recommends -y \
    libgfortran3 \
    libfftw3-dev \
    curl

RUN rm -rf /var/lib/apt/lists/*

RUN conda install -c conda-forge 'boto3>=1.4.4' 'psycopg2>=2.7.1' 'pyyaml>=3.12' 'lxml>=3.8.0' 'numpy>=1.13.0' 'pandas==0.23.0' 'scipy' 'bokeh' 'gdal' 'matplotlib' 'gmt=5.4.5' 'h5py'

# Pip is ran under /opt/conda/lib/python3.6/site-packages/pip
# Pip3 is ran under /usr/lib/python3/dist-packages
# Choose wisely
RUN pip install nbgitpuller asf-hyp3

# Install MapReady
COPY software/ASF_MapReady_cli.tar.gz /tmp/ASF_MapReady_cli.tar.gz
RUN cd /tmp/ && tar xzvf ASF_MapReady_cli.tar.gz && cd ASF_MapReady_cli && make install && rm -rf /tmp/ASF_MapReady*

# It's assumed that the compiled versions of previous libaries will have the same behavior
RUN cp /usr/lib/x86_64-linux-gnu/libgsl.so /usr/lib/x86_64-linux-gnu/libgsl.so.19
RUN cp /usr/lib/x86_64-linux-gnu/libproj.so /usr/lib/x86_64-linux-gnu/libproj.so.9
RUN cp /usr/lib/x86_64-linux-gnu/libhdf5_serial.so /usr/lib/x86_64-linux-gnu/libhdf5_serial.so.10
RUN cp /usr/lib/x86_64-linux-gnu/libnetcdf.so /usr/lib/x86_64-linux-gnu/libnetcdf.so.11

RUN wget -q -O /tmp/libpng12.deb http://mirrors.kernel.org/ubuntu/pool/main/libp/libpng/libpng12-0_1.2.54-1ubuntu1_amd64.deb \
    && dpkg -i /tmp/libpng12.deb \
    && rm /tmp/libpng12.deb


# Install ISCE.
ENV ISCE_HOME /usr/local/isce
ENV PYTHONPATH $PYTHONPATH:/usr/local/
ENV PATH $PATH:$ISCE_HOME/bin:$ISCE_HOME/applications

# This assumes that the ISCE package is a .zip found in .
COPY software/isce.zip /tmp/isce.zip
RUN cd /tmp/ && unzip isce.zip && mv isce $ISCE_HOME

# Add extra files to ISCE
COPY software/focus.py $ISCE_HOME/applications/
COPY software/topo.py $ISCE_HOME/applications/
COPY software/unpackFrame_ALOS_raw.py $ISCE_HOME/applications/

RUN chmod 755 $ISCE_HOME/applications/*


# Install SNAP
#RUN wget --no-verbose http://step.esa.int/downloads/5.0/installers/esa-snap_sentinel_unix_5_0.sh
COPY software/esa-snap_sentinel_unix_5_0.sh /usr/local/etc/esa-snap_sentinel_unix_5_0.sh
COPY software/snap_install.varfile /usr/local/etc/snap_install.varfile
RUN sh /usr/local/etc/esa-snap_sentinel_unix_5_0.sh -q -varfile /usr/local/etc/snap_install.varfile
COPY software/gpt.vmoptions /usr/local/snap/bin/gpt.vmoptions
RUN rm /usr/local/etc/esa-snap_sentinel_unix_5_0.sh


# Install GIAnT (which only runs in python 2)
#RUN pip2 install setuptools 'scipy==0.18.1' h5py lmxl 'matplotlib==2.0.2'
#RUN apt update --no-install-recommends && apt install python-tk python-configobj python-configparser && rm -rf /var/lib/apt/lists/*
#COPY software/GIAnT/ /usr/local/GIAnT/
#RUN python2.7 /usr/local/GIAnT/setup.py build_ext


# Get the git puller activated
RUN jupyter serverextension enable --py nbgitpuller --sys-prefix

USER jovyan
