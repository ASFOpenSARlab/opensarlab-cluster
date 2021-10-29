#!/bin/bash
set -e

python /etc/jupyter-hooks/resource_checks/check_storage.py $1

pip install --user \
    nbgitpuller \
    ipywidgets \
    mpldatacursor \
    rise \
    hide_code \
    jupyter_nbextensions_configurator \
    pandoc==2.0a4 \
    pypandoc

conda install -c conda-forge nb_conda_kernels

# copy over our version of pull.py
# REMINDER: REMOVE IF CHANGES ARE MERGED TO NBGITPULLER
cp /etc/jupyter-hooks/scripts/pull.py /home/jovyan/.local/lib/python3.8/site-packages/nbgitpuller/pull.py

# Add Path to local pip execs.
export PATH=$HOME/.local/bin:$PATH

jupyter serverextension enable --py nbgitpuller
jupyter nbextensions_configurator enable --user
jupyter nbextension enable --py widgetsnbextension --user
jupyter-nbextension enable rise --py --user
jupyter nbextension install --py hide_code --user
jupyter nbextension enable --py hide_code --user
jupyter serverextension enable --py hide_code --user

mkdir -p $HOME/.ipython/profile_default/startup/
cp /etc/jupyter-hooks/custom_magics/00-df.py $HOME/.ipython/profile_default/startup/00-df.py

gitpuller https://github.com/asfadmin/asf-jupyter-notebooks.git master $HOME/notebooks

gitpuller https://github.com/asfadmin/asf-jupyter-envs.git main $HOME/conda_environments

gitpuller https://github.com/asfadmin/asf-jupyter-docs.git master $HOME/opensarlab_docs
python /etc/jupyter-hooks/scripts/osl_user_guides_to_ipynb.py -p $HOME/opensarlab_docs

CONDARC=$HOME/.condarc
if ! test -f "$CONDARC"; then
cat <<EOT >> $CONDARC
channels:
  - conda-forge
  - defaults

channel_priority: strict

create_default_packages:
  - jupyter
  - kernda

envs_dirs:
  - /home/jovyan/.local/envs
  - /opt/conda/envs
EOT
fi

conda init

BASH_PROFILE=$HOME/.bash_profile
if ! test -f "$BASH_PROFILE"; then
cat <<EOT>> $BASH_PROFILE
if [ -s ~/.bashrc ]; then
    source ~/.bashrc;
fi
EOT
fi