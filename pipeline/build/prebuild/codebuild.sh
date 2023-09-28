
set -ex

export OSL_HOME=$CODEBUILD_SRC_DIR
export PYTHONPATH=$PYTHONPATH:$OSL_HOME/pipeline/build/prebuild/;
echo $OSL_HOME $PYTHONPATH;

echo "Check opensciencelab.yaml for required fields...";
python3 check_config.py \
    --config $OSL_HOME/opensciencelab.yaml;
yamllint -c $OSL_HOME/.yamllint $OSL_HOME/opensciencelab.yaml;

echo "Getting VpcId and Subnets...";
python3 get_vpcid_and_subnets.py \
    --region_name=${AWS_REGION} \
    --cluster_name=${COST_TAG_VALUE}-cluster \
    --config=$OSL_HOME/opensciencelab.yaml;
yamllint -c $OSL_HOME/.yamllint $OSL_HOME/opensciencelab.yaml;

echo "Render cf-cluster.yaml...";
python3 create_cf_cluster.py \
    --config $OSL_HOME/opensciencelab.yaml \
    --output_file $CODEBUILD_SRC_DIR/cf-cluster.yaml \
    --template_path $OSL_HOME/pipeline/cf-cluster.yaml.jinja;
yamllint -c $OSL_HOME/.yamllint $CODEBUILD_SRC_DIR/cf-cluster.yaml;
cfn-lint $CODEBUILD_SRC_DIR/cf-cluster.yaml