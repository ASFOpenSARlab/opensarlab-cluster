
set -ex

# ENV variables:
#   CRONS_FORCE_BUILD=true
#   DOCKER_REGISTRY=localhost:5000

if [ "$CRONS_FORCE_BUILD" = 'true' ]; then

    cp dockerfile dockerfile.build

    BUILD_TAG=$(date +"%F-%H-%M-%S")

    time docker build -f dockerfile.build -t $DOCKER_REGISTRY/crons:$BUILD_TAG -t $DOCKER_REGISTRY/crons:latest .

    # Push to registry
    docker push $DOCKER_REGISTRY/crons:$BUILD_TAG
    docker push $DOCKER_REGISTRY/crons:latest

    echo -n ${BUILD_TAG:-latest} > get_crons_image_build.tmp
fi
