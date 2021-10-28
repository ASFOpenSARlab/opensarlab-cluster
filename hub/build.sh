
set -ex

# ENV variables:
# DOCKER_REGISTRY

cp dockerfile dockerfile.build

BUILD_TAG=$(date +"%F-%H-%M-%S")

time docker build -f dockerfile.build -t $HUB_REPO_URI:$BUILD_TAG -t $HUB_REPO_URI:latest .

# Push to registry
docker push $HUB_REPO_URI:$BUILD_TAG
docker push $HUB_REPO_URI:latest

echo -n ${BUILD_TAG:-latest} > get_image_build.tmp
