##########
#
#   Create egress manifests from configs and then apply to minikube deployment
#
##########

set -ex

ROOTHERE=$(pwd)/../..
echo "Current root directory: $ROOTHERE"

# We need a good way to delete resources present in cluster but not in config without large service downturn
rm -rf $ROOTHERE/egress.yaml || true
rm $ROOTHERE/useretc/*.prepared || true

echo "Update egress yamls..."
python $ROOTHERE/render_egress.py \
    --configs-dir $ROOTHERE/useretc/ \
    --includes-dir $ROOTHERE/useretc/includes/ \
    --egress-template $ROOTHERE/egress.yaml.j2 \
    --egress-output-file $ROOTHERE/egress.yaml

echo "Linting egress k8s yamls..."
yamllint -c $ROOTHERE/../.yamllint $ROOTHERE/egress.yaml

echo "Apply Service Entry to namespace..."
kubectl apply --prune -f $ROOTHERE/egress.yaml \
    -l used-in-egress=yes \
    --prune-allowlist=core/v1/Namespace \
    --prune-allowlist=telemetry.istio.io/v1alpha1/Telemetry \
    --prune-allowlist=networking.istio.io/v1beta1/ServiceEntry \
    --prune-allowlist=networking.istio.io/v1beta1/DestinationRule \
    --prune-allowlist=networking.istio.io/v1beta1/VirtualService \
    --prune-allowlist=networking.istio.io/v1beta1/Sidecar \
    --prune-allowlist=networking.istio.io/v1alpha3/EnvoyFilter

# View cluster in UI
#minikube dashboard
