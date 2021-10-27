
set -ex

# ENV variables:
# DOCKER_REGISTRY

cp dockerfile dockerfile.build

BUILD_TAG=$(date +"%F-%H-%M-%S")

time docker build -f dockerfile.build -t $DOCKER_REPO:$BUILD_TAG -t $DOCKER_REPO:latest .

# Push to registry
docker push $DOCKER_REPO:$BUILD_TAG
docker push $DOCKER_REPO:latest

echo -n ${BUILD_TAG:-latest} > get_image_build.tmp
