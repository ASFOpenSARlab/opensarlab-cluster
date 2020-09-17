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
