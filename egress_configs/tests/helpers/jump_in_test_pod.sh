
SE_PROFILE=none

SOURCE_POD=$(kubectl -n jupyter get pod -l app=sleep -l opensciencelab.local/egress-profile=$SE_PROFILE -o jsonpath='{.items[0].metadata.name}')

kubectl -n jupyter exec -it $SOURCE_POD -- sh
