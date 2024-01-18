##########
#
#   Create egress manifests from configs and then apply to minikube deployment
#
##########

set -ex

ROOTHERE=$(pwd)/..
echo "Current root directory: $ROOTHERE"

# We need a good way to delete resources present in cluster but not in config without large service downturn
rm -rf $ROOTHERE/egress.yaml || true

echo "Update egress yamls..."
python $ROOTHERE/render_egress.py \
    --configs-dir $ROOTHERE/useretc/ \
    --includes-dir $ROOTHERE/useretc/includes/ \
    --egress-template $ROOTHERE/egress.yaml.j2 \
    --egress-output-file $ROOTHERE/egress.yaml

echo "Linting egress k8s yamls..."
yamllint -c $ROOTHERE/../.yamllint $ROOTHERE/egress.yaml

echo "Apply Service Entry to namespace..."
kubectl apply -f $ROOTHERE/egress.yaml

# View cluster in UI
#minikube dashboard
