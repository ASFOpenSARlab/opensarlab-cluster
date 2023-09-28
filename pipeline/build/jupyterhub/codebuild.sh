set -ex

#######
#  When calling script don't forget to prepend all the ingested environment variables
#
#    - AWS_AccountId=${AWS::AccountId} 
#       AWS_Region=${AWS::Region} 
#       ContainerNamespace=${ContainerNamespace} 
#       CostTagKey=${CostTagKey} 
#       CostTagValue=${CostTagValue} 
#       SECRET_SSO_TOKEN=$SECRET_SSO_TOKEN 
#       LabShortName=${LabShortName} 
#       PortalDomain=${PortalDomain} 
#       AdminUserName=${AdminUserName} 
#       NodeProxyPort=${NodeProxyPort} 
#       AZPostfix=${AZPostfix} 
#       DaysTillVolumeDeletion=${DaysTillVolumeDeletion} 
#       DaysTillSnapshotDeletion=${DaysTillSnapshotDeletion} 
#       SECRET_DH_CREDS=$SECRET_DH_CREDS 
#       CODEBUILD_ROOT=$CODEBUILD_ROOT 
#      bash codebuild.sh
#
#######

####### ******************
# Versions of software that need to be updated every cluster update
printf "\n\n%s\n" "******* ENV Variables (not including secrets):"
printf "%s\n" "
AWS_AccountId=${AWS_AccountId} 
AWS_Region=${AWS_Region} 
ContainerNamespace=${ContainerNamespace} 
CostTagKey=${CostTagKey} 
CostTagValue=${CostTagValue} 
LabShortName=${LabShortName} 
PortalDomain=${PortalDomain} 
AdminUserName=${AdminUserName} 
NodeProxyPort=${NodeProxyPort} 
AZPostfix=${AZPostfix} 
DaysTillVolumeDeletion=${DaysTillVolumeDeletion} 
DaysTillSnapshotDeletion=${DaysTillSnapshotDeletion} 
CODEBUILD_ROOT=${CODEBUILD_ROOT}
SECRET_SSO_TOKEN="
printf "%s\n\n" ${SECRET_SSO_TOKEN} | cut -c1-20

# https://docs.aws.amazon.com/eks/latest/userguide/install-kubectl.html
export KUBECTL_VERSION='1.24.7/2022-10-31'

# https://github.com/helm/helm/releases
export HELM_3_VERSION='v3.10.3'

# https://github.com/kubernetes-sigs/aws-ebs-csi-driver/releases
export AWS_EBS_CSI_DRIVER_VERSION='2.15.1'

# https://jupyterhub.github.io/helm-chart/
export JUPYTERHUB_HELM_VERSION='2.0.1-0.dev.git.5898.hc1abc4b9'  #'1.1.3-n772.hf133567f'

# https://docs.aws.amazon.com/eks/latest/userguide/managing-vpc-cni.html
export AWS_K8S_CNI_VERSION='v1.12.0'

# https://github.com/kubernetes/autoscaler/releases > cluster-autoscaler-chart
export CLUSTER_AUTOSCALER_HELM_VERSION='9.21.1'


####### ******************
# Install

pip3 install boto3 --upgrade
pip3 install kubernetes --upgrade
pip3 install jinja2 --upgrade

curl -o kubectl https://s3.us-west-2.amazonaws.com/amazon-eks/$KUBECTL_VERSION/bin/darwin/amd64/kubectl

curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash -s -- --version $HELM_3_VERSION

export HELM_HOST=127.0.0.1:44134
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp;
mv /tmp/eksctl /usr/local/bin;
eksctl version;


####### ******************
# Prebuild

printf "\n\n%s\n" "******* IAM build role used is... $(aws sts get-caller-identity)"

printf "\n\n%s\n" "******* Logging into AWS ECR...";
aws ecr get-login-password --region ${AWS_Region} | \
    docker login --username AWS --password-stdin ${AWS_AccountId}.dkr.ecr.${AWS_Region}.amazonaws.com

printf "\n\n%s\n" "******* Logging into Docker Hub user to get latest jupyter image...";
dh_username=$(echo ${SECRET_DH_CREDS} | cut -f1 -d' ');
echo ${SECRET_DH_CREDS} | cut -f2 -d' ' > dh.pass;
cat dh.pass | docker login -u $dh_username --password-stdin;

printf "\n\n%s\n" "******* Install helm charts and update...";
helm repo add jupyterhub https://jupyterhub.github.io/helm-chart/;
helm repo add autoscaler https://kubernetes.github.io/autoscaler;
helm repo add aws-ebs-csi-driver https://kubernetes-sigs.github.io/aws-ebs-csi-driver;
helm repo update;


####### *******************
# Build

printf "\n\n%s\n" "******* Get registry URI..";
export REGISTRY_URI=${AWS_AccountId}.dkr.ecr.${AWS_Region}.amazonaws.com/${ContainerNamespace}
printf "%s\n" "REGISTRY_URI: $REGISTRY_URI"

#######
printf "\n\n%s\n" "******* Update assumed role of cluster-build...";
cd ${CODEBUILD_ROOT}/pipeline/configs/;

cp cluster-build-assumerolepolicy.template.json assume.json;
sed -i "s|CLUSTER_RUN_ARN|arn:aws:iam::${AWS_AccountId}:role/${AWS_Region}-${CostTagValue}-cluster-run-role|" assume.json;
aws iam update-assume-role-policy --role-name ${AWS_Region}-${CostTagValue}-cluster-build-role --policy-document file://assume.json;
sleep 10

#######
printf "\n\n%s\n" "******* Update kubeconfig and apply config files...";
aws eks update-kubeconfig --name ${CostTagValue}-cluster --role-arn arn:aws:iam::${AWS_AccountId}:role/${AWS_Region}-${CostTagValue}-cluster-build-role;

#######
printf "\n\n%s\n" "******* Apply aws-auth.yaml...";
kubectl apply -f aws-auth-cm.yaml

#######
printf "\n\n%s\n" "******* Reapply storage class...";
kubectl delete sc gp2 || true;
kubectl apply -f csi-sc.yaml

#######
printf "\n\n%s\n" "******* Apply ebs csi driver...";
# if there is an error, then `kubectl delete csidriver ebs.csi.aws.com` and reapply. Warning: This will break volume management until reran.
helm upgrade aws-ebs-csi-driver aws-ebs-csi-driver/aws-ebs-csi-driver \
    --install \
    --version $AWS_EBS_CSI_DRIVER_VERSION \
    --namespace kube-system \
    --timeout=6m0s \
    --atomic \
    --set controller.extraCreateMetadata=true \
    --set controller.k8sTagClusterId=${CostTagValue}-cluster \
    --set controller.extraVolumeTags.${CostTagKey}=${CostTagValue}

#######
printf "\n\n%s\n" "******* Render Service Accounts...";
cd ${CODEBUILD_ROOT}/pipeline/build/jupyterhub/;
python3 service_accounts.py

#######
printf "\n\n%s\n" "******* Build and deploy custom Cron services...";
cd ${CODEBUILD_ROOT}/services/crons

cp dockerfile dockerfile.build;
export CRONS_IMAGE_BUILD=$(date +"%F-%H-%M-%S");
time docker build -f dockerfile.build -t $REGISTRY_URI/crons:$CRONS_IMAGE_BUILD -t $REGISTRY_URI/crons:latest .;
docker push $REGISTRY_URI/crons:$CRONS_IMAGE_BUILD;
docker push $REGISTRY_URI/crons:latest;

# Secret applied later
#sed -i "s|SSO_PLACEHOLDER|${SECRET_SSO_TOKEN}|" k8s/crons.yaml;
sed -i "s|IMAGE_PLACEHOLDER|$REGISTRY_URI/crons:$CRONS_IMAGE_BUILD|" k8s/crons.yaml;
kubectl apply -f k8s/crons.yaml;

#######
printf "\n\n%s\n" "******* Apply k8s resources for services...";
cd ${CODEBUILD_ROOT}/services
kubectl apply -f k8s.yaml

#######
printf "\n\n%s\n" "******* Build JupyterHub Image...";
cd ${CODEBUILD_ROOT}/jupyterhub/;

cp dockerfile dockerfile.build;
export HUB_IMAGE_BUILD=$(date +"%F-%H-%M-%S");
time docker build -f dockerfile.build -t $REGISTRY_URI/hub:$HUB_IMAGE_BUILD -t $REGISTRY_URI/hub:latest .;
docker push $REGISTRY_URI/hub:$HUB_IMAGE_BUILD;
docker push $REGISTRY_URI/hub:latest;

#######
printf "\n\n%s\n" "******* Various cluster env variables...";
printf "%s\n" "REGISTRY_URI $REGISTRY_URI";
printf "%s\n" "HUB_IMAGE_BUILD $HUB_IMAGE_BUILD";

#######
printf "\n\n%s\n" "******* Apply additional k8s resources: create sso-token-secret...";
kubectl create namespace jupyter --dry-run=client -o yaml | kubectl apply -f -
kubectl -n jupyter create secret generic sso-token-secret --save-config --dry-run=client --from-literal=sso_token="${SECRET_SSO_TOKEN}" -o yaml | kubectl apply -f -;
kubectl -n services create secret generic sso-token-secret --save-config --dry-run=client --from-literal=sso_token="${SECRET_SSO_TOKEN}" -o yaml | kubectl apply -f -;

#######
printf "\n\n%s\n" "******* Install JupyterHub cluster...";
cd ${CODEBUILD_ROOT}/jupyterhub/;
helm upgrade jupyter jupyterhub/jupyterhub \
    --install \
    --create-namespace \
    --namespace jupyter \
    --version $JUPYTERHUB_HELM_VERSION \
    --values helm_config.yaml \
    --timeout=6m0s \
    --atomic \
    --set hub.image.name=$REGISTRY_URI/hub \
    --set hub.image.tag=$HUB_IMAGE_BUILD \
    --set hub.baseUrl="/lab/${LabShortName}/" \
    --set hub.extraEnv.JUPYTERHUB_LAB_NAME="${LabShortName}" \
    --set hub.extraEnv.OPENSCIENCELAB_PORTAL_DOMAIN="${PortalDomain}" \
    --set hub.config.Authenticator.admin_users[0]=${AdminUserName} \
    --set proxy.service.nodePorts.http=${NodeProxyPort} \
    --set custom.REGISTRY_URI=$REGISTRY_URI \
    --set custom.CLUSTER_NAME="${CostTagValue}-cluster" \
    --set custom.AZ_NAME="${AWS_Region}${AZPostfix}" \
    --set custom.COST_TAG_VALUE="${CostTagValue}" \
    --set custom.COST_TAG_KEY="${CostTagKey}" \
    --set custom.DAYS_TILL_VOLUME_DELETION="${DaysTillVolumeDeletion}" \
    --set custom.DAYS_TILL_SNAPSHOT_DELETION="${DaysTillSnapshotDeletion}" \
    --set-file singleuser.extraFiles.user-hooks-sar.stringData='./singleuser/hooks/sar.sh' \
    --set-file singleuser.extraFiles.user-hooks-mapready.stringData='./singleuser/hooks/mapready.sh' \
    --set-file singleuser.extraFiles.user-hooks-mapready-no-git.stringData='./singleuser/hooks/mapready_no_git.sh' \
    --set-file singleuser.extraFiles.user-hooks-servir.stringData='./singleuser/hooks/servir.sh' \
    --set-file singleuser.extraFiles.user-hooks-sar_test.stringData='./singleuser/hooks/sar_test.sh' \
    --set-file singleuser.extraFiles.user-hooks-no_smart_git.stringData='./singleuser/hooks/no_smart_git.sh' \
    --set-file singleuser.extraFiles.user-hooks-pull.stringData='./singleuser/hooks/etc/pull.py' \
    --set-file singleuser.extraFiles.user-hooks-clean.stringData='./singleuser/hooks/etc/pkg_clean.py' \
    --set-file singleuser.extraFiles.user-hooks-kernel-flag.stringData='./singleuser/hooks/etc/old_kernels_flag.txt' \
    --set-file singleuser.extraFiles.user-hooks-kernel-flag-readme.stringData='./singleuser/hooks/etc/kernels_rename_README' \
    --set-file singleuser.extraFiles.user-others-check_storage.stringData='./singleuser/others/check_storage.py' \
    --set-file singleuser.extraFiles.user-custom_magics.stringData='./singleuser/custom_magics/00-df.py' \
    --set-file singleuser.extraFiles.user-template-page.stringData='./singleuser/templates/page.html' \
    --set-file singleuser.extraFiles.user-template-tree.stringData='./singleuser/templates/tree.html'

kubectl -n jupyter rollout status -w deployment.apps/hub

printf "\n\n%s\n" "******* Associate volume provisioner with service account...";
kubectl create clusterrolebinding cluster-pv --clusterrole=system:persistent-volume-provisioner --serviceaccount=jupyter:hub --dry-run=true -o yaml | kubectl apply -f -;

printf "\n\n%s\n" "******* Apply CNI. This must be updated on every cluster upgrade...";
curl -o aws-k8s-cni.yaml https://raw.githubusercontent.com/aws/amazon-vpc-cni-k8s/$AWS_K8S_CNI_VERSION/config/master/aws-k8s-cni.yaml;

sed -i "s/us-west-2/${AWS_Region}/" aws-k8s-cni.yaml;
kubectl apply -f aws-k8s-cni.yaml

#######
printf "\n\n%s\n" "******* Install autoscaler...";
helm upgrade autoscaler autoscaler/cluster-autoscaler \
    --install \
    --version $CLUSTER_AUTOSCALER_HELM_VERSION \
    --create-namespace \
    --namespace autoscaler \
    --atomic \
    --timeout=2m0s \
    --set autoDiscovery.clusterName=${CostTagValue}-cluster \
    --set awsRegion=${AWS_Region} \
    --set nodeSelector."hub\\.jupyter\\.org/node-purpose"=core


#######
printf "\n\n%s\n" "******* Install Fluent Bit for AWS Container Insights...";

export FluentBitHttpPort='2020';
export FluentBitReadFromHead='Off';

[[ $FluentBitReadFromHead = 'On' ]] && FluentBitReadFromTail='Off'|| FluentBitReadFromTail='On';
[[ -z $FluentBitHttpPort ]] && FluentBitHttpServer='Off' || FluentBitHttpServer='On';

curl https://raw.githubusercontent.com/aws-samples/amazon-cloudwatch-container-insights/latest/k8s-deployment-manifest-templates/deployment-mode/daemonset/container-insights-monitoring/quickstart/cwagent-fluent-bit-quickstart.yaml > cwagent-fluent-bit-quickstart.yaml;
sed -i "s|{{cluster_name}}|${CostTagValue}-cluster|" cwagent-fluent-bit-quickstart.yaml;
sed -i "s|{{region_name}}|${AWS_Region}|" cwagent-fluent-bit-quickstart.yaml;
sed -i "s|{{http_server_toggle}}|\"$FluentBitHttpServer\"|" cwagent-fluent-bit-quickstart.yaml;
sed -i "s|{{http_server_port}}|\"$FluentBitHttpPort\"|" cwagent-fluent-bit-quickstart.yaml;
sed -i "s|{{read_from_head}}|\"$FluentBitReadFromHead\"|" cwagent-fluent-bit-quickstart.yaml;
sed -i "s|{{read_from_tail}}|\"$FluentBitReadFromTail\"|" cwagent-fluent-bit-quickstart.yaml;
kubectl apply -f cwagent-fluent-bit-quickstart.yaml;

#######
printf "\n\n%s\n" "******* Install Prometheus for CloudWatch Insights";
cd ${CODEBUILD_ROOT}/pipeline/configs/;

sed -i "s|{{cluster_name}}|${CostTagValue}-cluster|; s|{{region_name}}|${AWS_Region}|" cwagent-prometheus.yaml;

kubectl apply -f cwagent-prometheus.yaml


printf "\n\n%s\n" "The End"
