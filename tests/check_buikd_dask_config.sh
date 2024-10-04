####
#
# Check some configs for integrity. This is meant to be used for local development. When pushing changes to code, please make sure artifacts created by this code are not present.
#
# run: 
#  python check_configs.sh
#
# Assume cfn-lint is present at root

ROOT_DIR=$(cd .. && pwd)

python3 $ROOT_DIR/pipeline/build/postbuild/create_dask_config.py \
    --config $ROOT_DIR/opensciencelab.yaml \
    --template_path $ROOT_DIR/pipeline/configs/dask_config.yaml.j2 \
    --output_file $ROOT_DIR/pipeline/configs/dask_config.yaml

yamllint -c $ROOT_DIR/.yamllint $ROOT_DIR/pipeline/configs/dask_config.yaml
