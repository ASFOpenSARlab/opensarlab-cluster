
set -ex

# Required ENV variables:
# NOTE_REPO_URI

cp dockerfile dockerfile.build

BUILD_TAG=$(date +"%F-%H-%M-%S")

time docker build -f dockerfile.build -t $NOTE_REPO_URI:$BUILD_TAG -t $NOTE_REPO_URI:latest .

# Push to registry
docker push $NOTE_REPO_URI:$BUILD_TAG
docker push $NOTE_REPO_URI:latest

echo -n ${BUILD_TAG:-latest} > get_image_build.tmp
