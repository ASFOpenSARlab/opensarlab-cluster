kubectl delete deploy --all -n istio-egress

kubectl delete destinationrules --all -A
kubectl delete envoyfilters --all -A
kubectl delete gateways --all -A
kubectl delete sidecars --all -A
kubectl delete serviceentry --all -A
kubectl delete virtualservices --all -A
kubectl delete workloadentries --all -A

kubectl delete pods --all -n jupyter
kubectl delete pods --all -n istio-system
kubectl delete pods --all -n istio-egress