
set -ex

export OSL_HOME=$CODEBUILD_SRC_DIR
export PYTHONPATH=$PYTHONPATH:$OSL_HOME/pipeline/1_prebuild/;
echo $OSL_HOME $PYTHONPATH;

echo "Check opensciencelab.yaml for required fields...";
python3 check_config.py \
    --config $OSL_HOME/useretc/opensciencelab.yaml;
yamllint -c $OSL_HOME/.yamllint $OSL_HOME/useretc/opensciencelab.yaml;

echo "Render cf-cluster.yaml...";
python3 create_cf_cluster.py \
    --config $OSL_HOME/useretc/opensciencelab.yaml \
    --output_file $OSL_HOME/cf-cluster.yaml \
    --template_path $OSL_HOME/pipeline/2_deploy_cluster/cf-cluster.yaml.jinja;
yamllint -c $OSL_HOME/.yamllint $OSL_HOME/cf-cluster.yaml;
cfn-lint $OSL_HOME/cf-cluster.yaml;

echo "Update egress yamls..."
python $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/egress/render_egress.py \
    --configs-dir $OSL_HOME/useretc/egress/ \
    --includes-dir $OSL_HOME/useretc/egress/includes/ \
    --egress-template $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/egress/egress.yaml.j2 \
    --egress-output-file $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/egress/egress.yaml

echo "Linting egress k8s yamls..."
yamllint -c $OSL_HOME/.yamllint $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/egress/egress.yaml
