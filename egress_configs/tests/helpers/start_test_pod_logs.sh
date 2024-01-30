
cd ..

K8S_NS=jupyter
SE_LAB=smce-test-opensarlab
SE_PROFILE=default

if [ ! -f "stern" ]; then
    # https://github.com/stern/stern/releases
    wget https://github.com/stern/stern/releases/download/v1.28.0/stern_1.28.0_linux_amd64.tar.gz
    tar -xzf stern_1.28.0_linux_amd64.tar.gz
fi

# Show logs of mulitple namespaces. The usual `kubectl logs` is rather limited
./stern . -n jupyter,istio-egress,istio-system --tail=0
