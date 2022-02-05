#!/bin/bash
set -ve

python /etc/jupyter-hooks/resource_checks/check_storage.py $1

# Add Path to local pip execs.
export PATH=$HOME/.local/bin:$PATH

python /etc/jupyter-hooks/scripts/pkg_clean.py

python -m pip install --user nbgitpuller

# copy over our version of pull.py
# REMINDER: REMOVE IF CHANGES ARE MERGED TO NBGITPULLER
cp /etc/jupyter-hooks/scripts/pull.py /home/jovyan/.local/lib/python3.9/site-packages/nbgitpuller/pull.py

# Disable the extension manager in Jupyterlab since server extensions are uninstallable
# by users and non-server extension installs do not persist over server restarts
jupyter labextension disable @jupyterlab/extensionmanager-extension

mkdir -p $HOME/.ipython/profile_default/startup/
cp /etc/jupyter-hooks/custom_magics/00-df.py $HOME/.ipython/profile_default/startup/00-df.py

# Update page and tree
mv /opt/conda/lib/python3.9/site-packages/notebook/templates/tree.html /opt/conda/lib/python3.9/site-packages/notebook/templates/original_tree.html
cp /etc/jupyter-hooks/templates/tree.html /opt/conda/lib/python3.9/site-packages/notebook/templates/tree.html

mv /opt/conda/lib/python3.9/site-packages/notebook/templates/page.html /opt/conda/lib/python3.9/site-packages/notebook/templates/original_page.html
cp /etc/jupyter-hooks/templates/page.html /opt/conda/lib/python3.9/site-packages/notebook/templates/page.html

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

KERNELS=$HOME/.local/share/jupyter/kernels
OLD_KERNELS=$HOME/.local/share/jupyter/kernels_old
FLAG=$HOME/.jupyter/old_kernels_flag.txt
if ! test -f "$FLAG" && test -d "$KERNELS"; then
cp /etc/jupyter-hooks/etc/old_kernels_flag.txt $HOME/.jupyter/old_kernels_flag.txt
mv $KERNELS $OLD_KERNELS
cp /etc/jupyter-hooks/etc/kernels_rename_README $OLD_KERNELS/kernels_rename_README
fi

# Add a CondaKernelSpecManager section to jupyter_notebook_config.json to display nicely formatted kernel names
JN_CONFIG=$HOME/.jupyter/jupyter_notebook_config.json
if ! test -f "$JN_CONFIG"; then
echo '{}' > "$JN_CONFIG"
fi

if ! grep -q "\"CondaKernelSpecManager\":" "$JN_CONFIG"; then
jq '. += {"CondaKernelSpecManager": {"name_format": "{display_name}"}}' "$JN_CONFIG" >> temp;
mv temp "$JN_CONFIG";
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