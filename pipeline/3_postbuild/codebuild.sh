
set -ex

export OSL_HOME=${CODEBUILD_SRC_DIR};
export PYTHONPATH=$PYTHONPATH:${CODEBUILD_SRC_DIR}/pipeline/3_postbuild/;
echo $OSL_HOME $PYTHONPATH;

echo "Update lab_domain...";
python3 update_lab_domain.py \
    --config=$OSL_HOME/useretc/opensciencelab.yaml \
    --aws_region=${AWS_REGION} ;

echo "Render aws-auth-cm.yaml...";
python3 create_aws_auth.py \
    --config $OSL_HOME/useretc/opensciencelab.yaml \
    --output_file $OSL_HOME/pipeline/4_deploy_and_build_jupyter/configs/aws-auth-cm.yaml \
    --template_path $OSL_HOME/pipeline/4_deploy_and_build_jupyter/configs/aws-auth-cm.yaml.jinja \
    --region_name ${AWS_REGION} \
    --account_id ${AWS_ACCOUNT_ID} ;
yamllint -c $OSL_HOME/.yamllint $OSL_HOME/pipeline/4_deploy_and_build_jupyter/configs/aws-auth-cm.yaml;

echo "Render service_accounts.py...";
python3 create_service_accounts.py \
    --config $OSL_HOME/useretc/opensciencelab.yaml \
    --output_file $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/services/service_accounts.py \
    --template_path $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/services/service_accounts.py.jinja \
    --region_name ${AWS_REGION} \
    --cluster_name=${COST_TAG_VALUE}-cluster ;

echo "Render crons.yaml...";
python3 create_crons.py \
    --config $OSL_HOME/useretc/opensciencelab.yaml \
    --template_path $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/services/crons/k8s/crons.yaml.jinja \
    --output_file $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/services/crons/k8s/crons.yaml \
    --region_name ${AWS_REGION} \
    --cluster_name=${COST_TAG_VALUE}-cluster ;
yamllint -c $OSL_HOME/.yamllint $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/services/crons/k8s/crons.yaml;

echo "Render singleuser scripts...";
python3 create_singleuser_scripts.py \
    --origin_singleuser_scripts_dir $OSL_HOME/useretc/hooks/ \
    --dest_hook_scripts_dir $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/jupyterhub/singleuser/hooks/ \
    --dest_extension_override_dir $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/jupyterhub/singleuser/overrides/ \
    --helm_config_template $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/jupyterhub/helm_config.yaml.j2 \
    --helm_config $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/jupyterhub/helm_config.yaml \
    --jupyterhub_codebuild_template $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/codebuild.sh.j2 \
    --jupyterhub_codebuild $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/codebuild.sh ;

echo "Render files within jupyterhub_config.d...";
python3 create_config_d.py \
    --config $OSL_HOME/useretc/opensciencelab.yaml \
    --work_dir $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/jupyterhub/config.d/ ;

echo "Rendering cf-jupyterhub.yaml...";
python3 create_cf_jupyterhub.py \
    --config $OSL_HOME/useretc/opensciencelab.yaml \
    --output_file $OSL_HOME/cf-jupyterhub.yaml \
    --template_path $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/cf-jupyterhub.yaml.jinja ;
yamllint -c $OSL_HOME/.yamllint $OSL_HOME/cf-jupyterhub.yaml;
cfn-lint $OSL_HOME/cf-jupyterhub.yaml;

echo "Rendering possible_profiles.py....";
python3 create_possible_profiles.py \
    --config $OSL_HOME/useretc/opensciencelab.yaml \
    --output_file $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/jupyterhub/hub/web/usr/local/lib/jupyterhub/handlers/possible_profiles.py \
    --template_path $OSL_HOME/pipeline/4_deploy_and_build_jupyterhub/jupyterhub/hub/web/usr/local/lib/jupyterhub/handlers/possible_profiles.py.j2;
