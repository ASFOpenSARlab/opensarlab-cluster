
set -ex

# ENV variables:
# HUB_FORCE_BUILD=true
# DOCKER_REGISTRY

if [ "$HUB_FORCE_BUILD" = 'true' ]; then

    cp dockerfile dockerfile.build

    BUILD_TAG=$(date +"%F-%H-%M-%S")

    time docker build -f dockerfile.build --target testing .
    time docker build -f dockerfile.build -t $DOCKER_REGISTRY/hub:$BUILD_TAG -t $DOCKER_REGISTRY/hub:latest --target release .

    # Push to registry
    docker push $DOCKER_REGISTRY/hub:$BUILD_TAG
    docker push $DOCKER_REGISTRY/hub:latest

    export HubBuildTag=$BUILD_TAG
fi
