
K8S_NS=jupyter
SE_LAB=smce-test-opensarlab
SE_PROFILE=default

SOURCE_POD=$(kubectl -n $K8S_NS get pod -l app=sleep -l se-lab=$SE_LAB -l se-profile=$SE_PROFILE -o jsonpath='{.items[0].metadata.name}')

kubectl -n jupyter exec -it $SOURCE_POD -- sh
