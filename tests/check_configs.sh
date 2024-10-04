####
#
# Check some configs for integrity. This is meant to be used for local development. When pushing changes to code, please make sure artifacts created by this code are not present.
#
# run: 
#  python check_configs.sh
#
# Assume cfn-lint is present at root

ROOT_DIR=$(cd .. && pwd)

python3 $ROOT_DIR/pipeline/build/prebuild/check_config.py --config $ROOT_DIR/opensciencelab.yaml
yamllint -c $ROOT_DIR/.yamllint $ROOT_DIR/opensciencelab.yaml


python3 $ROOT_DIR/pipeline/build/prebuild/create_cf_cluster.py --config $ROOT_DIR/opensciencelab.yaml --output_file $ROOT_DIR/pipeline/cf-cluster.yaml --template_path $ROOT_DIR/pipeline/cf-cluster.yaml.jinja
yamllint -c $ROOT_DIR/.yamllint $ROOT_DIR/pipeline/cf-cluster.yaml
cfn-lint $ROOT_DIR/pipeline/cf-cluster.yaml
