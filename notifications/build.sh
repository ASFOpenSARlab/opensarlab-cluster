
set -ex

# ENV variables:
# NOTIFICATIONS_FORCE_BUILD=true
# DOCKER_REGISTRY

if [ "$NOTIFICATIONS_FORCE_BUILD" = 'true' ]; then

    cp dockerfile dockerfile.build

    BUILD_TAG=$(date +"%F-%H-%M-%S")

    time docker build -f dockerfile.build -t $DOCKER_REGISTRY/notifications:$BUILD_TAG -t $DOCKER_REGISTRY/notifications:latest .

    # Push to registry
    docker push $DOCKER_REGISTRY/notifications:$BUILD_TAG
    docker push $DOCKER_REGISTRY/notifications:latest
fi
