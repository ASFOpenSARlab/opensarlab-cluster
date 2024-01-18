
K8S_NS=jupyter
SE_LAB=smce-test-opensarlab
SE_PROFILE=default

if [[ -z "kubetail" ]]; then
    wget "https://raw.githubusercontent.com/johanhaleby/kubetail/master/kubetail"
fi

## WIP
./kubetail --all-namespaces -l sidecar.istio.io/inject=true --follow

#SOURCE_POD=$(kubectl -n $K8S_NS get pod -l app=sleep -l se-lab=$SE_LAB -l se-profile=$SE_PROFILE -o jsonpath='{.items[0].metadata.name}')
#kubectl -n istio-egress logs -l sidecar.istio.io/inject=true --follow
#kubectl -n istio-system logs -l sidecar.istio.io/inject=true --follow
#kubectl -n $K8S_NS logs -l sidecar.istio.io/inject=true --follow
