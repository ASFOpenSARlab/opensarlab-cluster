FROM jupyter/minimal-notebook:83ed2c63671f
LABEL MAINTAINER="Alaska Satellite Facility"

# By default, the notebook base image is set to non-sudo user joyvan. This makes root-ful actions difficult.
USER root

# Pip is ran under /opt/conda/lib/python3.6/site-packages/pip.
# Pip3 is ran under /usr/lib/python3.6/dist-packages.
# Pip2 is ran under /usr/lib/python2.7/dist-packages. Choose wisely.

# Manually update nbconvert. A dicrepancy in the versioning causes a 500 when opening a notebook. https://github.com/jupyter/notebook/issues/3629#issuecomment-399408222
# Remember, here pip is updating within the condas namespace where jupyter notebook items are held.
RUN pip install --upgrade nbconvert

# Downgrade tornado otherwise the notebook can't connect to the notebook server. https://github.com/jupyter/notebook/issues/2664#issuecomment-468954423
RUN pip install tornado==4.5.3

# ---------------------------------------------------------------------------------------------------------------
# Install general items. If a library is needed for a specific piece of software, put it with that software.
RUN apt update && \
    apt install --no-install-recommends -y software-properties-common && \
    add-apt-repository -y ppa:ubuntugis/ubuntugis-unstable

RUN apt update && \
    apt install --no-install-recommends -y \
    python3 \
    python3-pip \
    python2.7 \
    python-pip \
    python2.7-setuptools \
    python3-setuptools \
    zip \
    wget \
    awscli \
    vim \
    rsync \
    less

RUN pip install 'boto3>=1.4.4' 'pyyaml>=3.12' 'pandas==0.23.0' 'bokeh' 'matplotlib' 'tensorflow==1.13.1'


# ---------------------------------------------------------------------------------------------------------------
# Install MapReady
RUN apt update && \
    apt install --no-install-recommends -y \
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

COPY software/ASF_MapReady /tmp/ASF_MapReady
RUN cd /tmp/ASF_MapReady && make install && rm -rf /tmp/ASF_MapReady*

# It's assumed that the compiled versions of previous libaries will have the same behavior
RUN cp /usr/lib/x86_64-linux-gnu/libgsl.so /usr/lib/x86_64-linux-gnu/libgsl.so.19
RUN cp /usr/lib/x86_64-linux-gnu/libproj.so /usr/lib/x86_64-linux-gnu/libproj.so.9
RUN cp /usr/lib/x86_64-linux-gnu/libhdf5_serial.so /usr/lib/x86_64-linux-gnu/libhdf5_serial.so.10
RUN cp /usr/lib/x86_64-linux-gnu/libnetcdf.so /usr/lib/x86_64-linux-gnu/libnetcdf.so.11

RUN wget -q -O /tmp/libpng12.deb http://mirrors.kernel.org/ubuntu/pool/main/libp/libpng/libpng12-0_1.2.54-1ubuntu1_amd64.deb \
    && dpkg -i /tmp/libpng12.deb \
    && rm /tmp/libpng12.deb


# ---------------------------------------------------------------------------------------------------------------
# Install ISCE.

RUN apt update && \
    apt install --no-install-recommends -y \
    gdal-bin \
    gfortran \
    libgfortran3 \
    libfftw3-dev \
    curl

RUN pip install 'numpy>=1.13.0' 'h5py' 'gdal' 'scipy'

ENV ISCE_HOME /usr/local/isce
ENV PYTHONPATH $PYTHONPATH:/usr/local/
ENV PATH $PATH:$ISCE_HOME/bin:$ISCE_HOME/applications

COPY software/isce $ISCE_HOME

# Add extra files to ISCE
COPY software/focus.py $ISCE_HOME/applications/
COPY software/topo.py $ISCE_HOME/applications/
COPY software/unpackFrame_ALOS_raw.py $ISCE_HOME/applications/

RUN chmod 755 $ISCE_HOME/applications/*


# ---------------------------------------------------------------------------------------------------------------
# Install SNAP
COPY software/esa-snap_sentinel_unix_5_0.sh /usr/local/etc/esa-snap_sentinel_unix_5_0.sh
COPY software/snap_install.varfile /usr/local/etc/snap_install.varfile
RUN sh /usr/local/etc/esa-snap_sentinel_unix_5_0.sh -q -varfile /usr/local/etc/snap_install.varfile
COPY software/gpt.vmoptions /usr/local/snap/bin/gpt.vmoptions
RUN rm /usr/local/etc/esa-snap_sentinel_unix_5_0.sh


# ---------------------------------------------------------------------------------------------------------------
# Install GIAnT (which only runs in python 2)
# Some of these might not be needed but the thing works.
RUN apt install -y build-essential \
    gfortran \
    zlibc \
    zlib1g-dev \
    libpng-dev \
    libopenjp2-7-dev \
    environment-modules \
    libopenblas-dev \
    libfreetype6-dev \
    pkg-config \
    cython \
    ipython \
    python-pip \
    python-numpy \
    python-scipy \
    python-numexpr \
    python-setuptools \
    python-distutils-extra \
    python-matplotlib \
    python-h5py \
    python-pyproj \
    python-mpltoolkits.basemap \
    python-lxml \
    python-requests \
    python-gdal \
    python-pyshp \
    python-shapely \
    python-pywt \
    python-simplejson \
    python-netcdf4 \
    python-pyresample

RUN pip2 install 'scipy==0.18.1' 'matplotlib==1.4.3' 'pykml'

COPY software/GIAnT/ /usr/local/GIAnT/
RUN cd /usr/local/GIAnT/ && python2.7 setup.py build_ext
ENV PYTHONPATH $PYTHONPATH:/usr/local/GIAnT

COPY software/prepdataxml.py /usr/local/GIAnT/prepdataxml.py


# ---------------------------------------------------------------------------------------------------------------
# Install any other custom and jupyter libaries
# Use pip (conda version) since we want to corner off GIAnT's work and also run it with Jupyter
RUN pip install nbgitpuller asf-hyp3

# Get the git puller activated
RUN jupyter serverextension enable --py nbgitpuller --sys-prefix



RUN rm -rf /var/lib/apt/lists/*

USER jovyan
