
set -ex

export OSL_HOME=$CODEBUILD_SRC_DIR
export PYTHONPATH=$PYTHONPATH:$OSL_HOME/pipeline/build/prebuild/;
echo $OSL_HOME $PYTHONPATH;

echo "Check opensciencelab.yaml for required fields...";
python3 check_config.py \
    --config $OSL_HOME/opensciencelab.yaml;
yamllint -c $OSL_HOME/.yamllint $OSL_HOME/opensciencelab.yaml;

echo "Render cf-cluster.yaml...";
python3 create_cf_cluster.py \
    --config $OSL_HOME/opensciencelab.yaml \
    --output_file $CODEBUILD_SRC_DIR/cf-cluster.yaml \
    --template_path $OSL_HOME/pipeline/cf-cluster.yaml.jinja;
yamllint -c $OSL_HOME/.yamllint $CODEBUILD_SRC_DIR/cf-cluster.yaml;
cfn-lint $CODEBUILD_SRC_DIR/cf-cluster.yaml;

echo "Update egress yamls..."
python $OSL_HOME/egress_configs/render_egress.py \
    --configs-dir $OSL_HOME/egress_configs/useretc/ \
    --includes-dir $OSL_HOME/egress_configs/useretc/includes/ \
    --egress-template $OSL_HOME/egress_configs/egress.yaml.j2 \
    --egress-output-file $OSL_HOME/egress_configs/egress.yaml

echo "Linting egress k8s yamls..."
yamllint -c $OSL_HOME/.yamllint $OSL_HOME/egress_configs/egress.yaml
