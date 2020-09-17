#!/bin/bash

# These are a set of AWS commands that build out resouces outside Cloudformation
# These are meant to be created once and do not need to be overriden (accidently or otherwise) on subsequent builds.
# Most of these are required, though may be removed if no longer used
# The following assume that the AWS account has been created and the local AWS config file is configured properly

if [[ "$#" == 0 ]] ; then
   PROFILE=default
elif [[ "$#" == 1 ]] ; then
   PROFILE=$1
fi

echo "Using AWS profile '$PROFILE'"

#### User Params
MY_DOCKER_HUB_CREDS=asfdaac:myPassword


#### Roles 

#### Cognito 

#### Secret Manager
echo "Creating Docker Hub secret entry. Password needs to be updated manually..."
# Create secret for Docker Hub user to be used in image pulls
# To retrieve: aws --profile=$PROFILE secretsmanager get-secret-value --secret-id dockerhub/creds --version-stage AWSCURRENT
aws --profile=$PROFILE secretsmanager create-secret --name dockerhub/creds --description "Docker Hub Username/Password" --secret-string $MY_DOCKER_HUB_CREDS

exit 


################################################################
# Other helps for upgrading and conversion

# Update cluster when Helm 2 -> 3 locally
# This assumes that helm and kubeconfig are installed and configured properly

# First way:
# https://helm.sh/docs/topics/v2_v3_migration/
# Install the converter and convert cluster in place
helm plugin install https://github.com/helm/helm-2to3.git
helm list 
helm 2to3 convert jupyter --dry-run --tiller-out-cluster  # Or whatever the release name is
# If the dry run throws no errors, run for real
helm 2to3 convert jupyter --tiller-out-cluster

# If the previous doesn't work (though it should) then do the following:
# If on build the release fails complaining about lack of annotations, apply the following
# https://github.com/helm/helm/issues/7697#issuecomment-613535044

for n in $(kubectl get ns -o name | cut -c11-)
do
    echo "Namespace '$n'"
    for r in $(kubectl api-resources --verbs=list -o name | xargs -n 1 kubectl get -o name --ignore-not-found -l chart -n $n)
    do
        echo "Resource '$r' in namespace '$n'"
        kubectl -n $n annotate --overwrite $r meta.helm.sh/release-name=$n
        kubectl -n $n annotate --overwrite $r meta.helm.sh/release-namespace=$n
        kubectl -n $n label --overwrite $r app.kubernetes.io/managed-by=Helm
    done
done

# Also pickup any labelled with Tiller
for n in $(kubectl get ns -o name | cut -c11-)
do
    echo "Namespace '$n'"
    for r in $(kubectl api-resources --verbs=list -o name | xargs -n 1 kubectl get -o name --ignore-not-found -l app.kubernetes.io/managed-by=Tiller -n $n)
    do
        echo "Resource '$r' in namespace '$n'"
        kubectl -n $n annotate --overwrite $r meta.helm.sh/release-name=$n
        kubectl -n $n annotate --overwrite $r meta.helm.sh/release-namespace=$n
        kubectl -n $n label --overwrite $r app.kubernetes.io/managed-by=Helm
    done
done

# There will likely be others not picked up. These will need to be handled by hand as any failures show what needs to be changed during build.

#######################
# Update cluster versions https://docs.aws.amazon.com/eks/latest/userguide/update-cluster.html

# 1. Spin down all autoscaler to 0 nodes. Remain here till upgrade is complete.  

# 2. Update cluster manually to 1.16 in AWS console. Refrsh the page and check the Updates tab since the console is broken on dispalying status.

# 3. Check current kube-proxy image for right region and cluster address
kubectl get daemonset kube-proxy --namespace kube-system -o=jsonpath='{$.spec.template.spec.containers[:1].image}'
# 602401143452.dkr.ecr.us-east-1.amazonaws.com/eks/kube-proxy:v1.15.11-eksbuild.1

# 4. Apply new image for 1.16
kubectl set image daemonset.apps/kube-proxy -n kube-system kube-proxy=602401143452.dkr.ecr.us-east-1.amazonaws.com/eks/kube-proxy:v1.16.13-eksbuild.1

# 5. This should not be needed if the chart makers are keeping things up-to-date.
# If not, a patch will need to be made during build via something like `kubectl convert -f ./my-deployment.yaml --output-version apps/v1`
#kubectl patch psp -p {"apiVersion":"policy/v1beta1"}'  # apiVersion: extensions/v1beta1 => apiVersion: policy/v1beta1

# 6. Update cluster manually to 1.17

# 7. Apply new image for 1.17
kubectl set image daemonset.apps/kube-proxy -n kube-system kube-proxy=602401143452.dkr.ecr.us-east-1.amazonaws.com/eks/kube-proxy:v1.17.9-eksbuild.1

# 8. Update cloudformation template parameters 
#       NodeImageIdGPU.default  => /aws/service/eks/optimized-ami/1.17/amazon-linux-2-gpu/recommended/image_id
#       NodeImageIdCPU.default  => /aws/service/eks/optimized-ami/1.17/amazon-linux-2/recommended/image_id
#       NodeImageIdCPULarge.default  => /aws/service/eks/optimized-ami/1.17/amazon-linux-2/recommended/image_id
#       NodeImageIdCore.default  => /aws/service/eks/optimized-ami/1.17/amazon-linux-2/recommended/image_id

# 9. Redeploy build via codepipeline

# 10. Autoscale nodes back to default values (1,2,etc)
