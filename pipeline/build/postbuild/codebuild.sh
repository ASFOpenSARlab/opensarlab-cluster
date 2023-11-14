
set -ex

export OSL_HOME=${CODEBUILD_SRC_DIR};
export PYTHONPATH=$PYTHONPATH:${CODEBUILD_SRC_DIR}/pipeline/build/postbuild/;
echo $OSL_HOME $PYTHONPATH;

echo "Update lab_domain...";
python3 update_lab_domain.py \
    --config=$OSL_HOME/opensciencelab.yaml \
    --aws_region=${AWS_REGION} ;

echo "Render aws-auth-cm.yaml...";
python3 create_aws_auth.py \
    --config $OSL_HOME/opensciencelab.yaml \
    --output_file $OSL_HOME/pipeline/configs/aws-auth-cm.yaml \
    --template_path $OSL_HOME/pipeline/configs/aws-auth-cm.yaml.jinja \
    --region_name ${AWS_REGION} \
    --account_id ${AWS_ACCOUNT_ID} ;
yamllint -c $OSL_HOME/.yamllint $OSL_HOME/pipeline/configs/aws-auth-cm.yaml;

echo "Render service_accounts.py...";
python3 create_service_accounts.py \
    --config $OSL_HOME/opensciencelab.yaml \
    --output_file $OSL_HOME/pipeline/build/jupyterhub/service_accounts.py \
    --template_path $OSL_HOME/pipeline/build/jupyterhub/service_accounts.py.jinja \
    --region_name ${AWS_REGION} \
    --cluster_name=${COST_TAG_VALUE}-cluster ;

echo "Render crons.yaml...";
python3 create_crons.py \
    --config $OSL_HOME/opensciencelab.yaml \
    --template_path $OSL_HOME/services/crons/k8s/crons.yaml.jinja \
    --output_file $OSL_HOME/services/crons/k8s/crons.yaml \
    --region_name ${AWS_REGION} \
    --cluster_name=${COST_TAG_VALUE}-cluster ;
yamllint -c $OSL_HOME/.yamllint $OSL_HOME/services/crons/k8s/crons.yaml;

echo "Render singleuser scripts...";
python3 create_singleuser_scripts.py \
    --origin_singleuser_scripts_dir=$OSL_HOME/singleuser/ \
    --dest_hook_scripts_dir=$OSL_HOME/jupyterhub/singleuser/hooks/ \
    --dest_extension_override_dir=$OSL_HOME/jupyterhub/singleuser/extension_overrides/ \
    --helm_config_template=$OSL_HOME/jupyterhub/helm_config.yaml.j2 \
    --helm_config=$OSL_HOME/jupyterhub/helm_config.yaml \
    --jupyterhub_codebuild_template=$OSL_HOME/pipeline/build/jupyterhub/codebuild.sh.j2 \
    --jupyterhub_codebuild=$OSL_HOME/pipeline/build/jupyterhub/codebuild.sh ;

echo "Render files within jupyterhub_config.d...";
python3 create_config_d.py \
    --config $OSL_HOME/opensciencelab.yaml \
    --work_dir $OSL_HOME/jupyterhub/config.d/ ;

echo "Rendering cf-jupyterhub.yaml...";
python3 create_cf_jupyterhub.py \
    --config $OSL_HOME/opensciencelab.yaml \
    --output_file ${CODEBUILD_SRC_DIR}/cf-jupyterhub.yaml \
    --template_path $OSL_HOME/pipeline/cf-jupyterhub.yaml.jinja ;
yamllint -c $OSL_HOME/.yamllint ${CODEBUILD_SRC_DIR}/cf-jupyterhub.yaml;
cfn-lint ${CODEBUILD_SRC_DIR}/cf-jupyterhub.yaml;

echo "Rendering possible_profiles.py....";
python3 create_possible_profiles.py \
    --config $OSL_HOME/opensciencelab.yaml \
    --output_file $OSL_HOME/jupyterhub/hub/web/usr/local/lib/jupyterhub/handlers/possible_profiles.py \
    --template_path $OSL_HOME/jupyterhub/hub/web/usr/local/lib/jupyterhub/handlers/possible_profiles.py.j2 ;
