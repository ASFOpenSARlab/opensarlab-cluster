#######
#
#   Setup up Minikube and Istio for local dev and testing
#
#   Works for Ubuntu, but should be adaptable to other OSes
#
#######

# Install Helm. https://helm.sh/docs/intro/install/

# Install Kubectl. https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/

# Install a local K8s
# https://minikube.sigs.k8s.io/docs/start/

# Remove current k8s config so we don't accidently update some other remote cluster
rm ~/.kube/config

# Start cluster 
minikube start

# Make sure proper EKS cluster is being used
kubectl cluster-info

######
cd ..

echo "Install Istio client..."
curl -L https://istio.io/downloadIstio | ISTIO_VERSION=1.19.3 TARGET_ARCH=x86_64 sh - && \
    cd istio-1.19.3 && \
    export PATH="$PATH:$PWD/bin"
istioctl x precheck


echo "Install Istio..."
istioctl install -y --set profile=minimal \
    ##--set meshConfig.outboundTrafficPolicy.mode=REGISTRY_ONLY \
    --set meshConfig.outboundTrafficPolicy.mode=ALLOW_ANY \
    --set meshConfig.accessLogFile=/dev/stdout
    #--set components.cni.enabled=true

# Check for REGISTRY_ONLY or ALLOW_ANY
kubectl get configmap istio -n istio-system -o jsonpath='{.data.mesh}'

# Inject just to pod
# kubectl label -n default pod/the_pod sidecar.istio.io/inject="true"

#cat <<EOF > /tmp/istio-cni.yaml
#apiVersion: install.istio.io/v1alpha1
#kind: IstioOperator
#spec:
#  components:
#    cni:
#      enabled: true
#EOF
#istioctl install -f /tmp/istio-cni.yaml -y

# ??
# Add discovery charts so that only certain pods are "visible" by the mesh. This will reduce resource usage.
# ...


#### Test application in default namespace
SE_PROFILE=none

echo "Install small container called "sleep" for playing around with..."
kubectl create namespace jupyter --dry-run=client -o yaml | kubectl apply -f -
kubectl label namespace jupyter istio-injection=enabled --overwrite
kubectl -n jupyter apply -f https://raw.githubusercontent.com/istio/istio/release-1.19/samples/sleep/sleep.yaml
kubectl -n jupyter patch deployments/sleep -p '{"spec":{"template":{"metadata":{"labels":{"opensciencelab.local/egress-profile":"'$SE_PROFILE'"}}}}}'
kubectl scale --replicas=1 deployment sleep -n jupyter


# Other cleanup...
#minikube pause
#minikube stop
#minikube delete --all