#!/bin/bash
set -e

which python
which pip
which conda
which jupyter

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
cp /etc/jupyter-hooks/scripts/pull.py /home/jovyan/.local/lib/python3.9/site-packages/nbgitpuller/pull.py

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

# Update page and tree
mv /opt/conda/lib/python3.9/site-packages/notebook/templates/tree.html /opt/conda/lib/python3.9/site-packages/notebook/templates/original_tree.html
mv /etc/jupyter-hooks/templates/tree.html /opt/conda/lib/python3.9/site-packages/notebook/templates/tree.html

mv /opt/conda/lib/python3.9/site-packages/notebook/templates/page.html /opt/conda/lib/python3.9/site-packages/notebook/templates/original_page.html
mv /etc/jupyter-hooks/templates/page.html /opt/conda/lib/python3.9/site-packages/notebook/templates/page.html

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