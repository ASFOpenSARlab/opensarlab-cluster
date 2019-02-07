This is largely taken from https://z2jh.jupyter.org/en/latest/amazon/step-zero-aws.html and https://kubernetes.io/docs/setup/custom-cloud/kops/
To simplify AWS management, a subaccount was created in AWS called JupyterHub that contains only the following.

###Install the k8s cluster in AWS

1. Create a IAM Role

    Name: `jupyterhub-cluster`
    - AmazonEC2FullAccess
    - IAMFullAccess
    - AmazonS3FullAccess
    - AmazonVPCFullAccess
    - Route53FullAccess (Optional. This is useful later for url routing if wanted)

2. Create a Ec2 instance that will be the cluster master

    - type: AWS Linux
    - size: t2.micro
    - IAM role: jupyterhub-cluster
    - keypair: Create a new pair and save on your local machine

    On creation, note the public ip.

3. SSH into the cluster master
    
    `ssh -i my-key.pem ec2-user@cluster-master-public-ip`

4. Install `kops` on the cluster master. https://github.com/kubernetes/kops/blob/master/docs/install.md

    ```
    curl -Lo kops https://github.com/kubernetes/kops/releases/download/$(curl -s https://api.github.com/repos/kubernetes/kops/releases/latest | grep tag_name | cut -d '"' -f 4)/kops-linux-amd64
    chmod +x ./kops
    sudo mv ./kops /usr/local/bin/
    ```
    To check installation, type `kops` on the command line.

    We are keeping kops only on the cluster master for security reasons. any changes to the cluster will need to be done only within the ec2.

5. Create a keypair to be used by the cluster and other AWS resources

    `ssh-keygen`
    
    Skip the name and passphrase. Save in the rsa public default.

6. Manually create s3 bucket named `asf-jupyter-cluster` (or something similar. Remember that it has to be globally unique.)

    This bucket will contain cluster metadata used by kops. The docs recommmend that versioning be turned on.

7. Create some enviroment varibles: cluster name, bucket name, region, and AZs.

    ```bash
    export NAME=jupyter.k8s.local
    export KOPS_STATE_STORE=s3://asf-jupyter-cluster
    export REGION=`curl -s http://169.254.169.254/latest/dynamic/instance-identity/document|grep region|awk -F\" '{print $4}'` 
    export ZONES=$(aws ec2 describe-availability-zones --region $REGION | grep ZoneName | awk '{print $2}' | tr -d '"')
    export ZONES=$(echo $ZONES | tr -d " " | rev | cut -c 2- | rev)
    ```
8. Create k8s cluster. 

    The cluster will have a master ec2 and a number of slave ec2 nodes. These slave ec2 nodes will contain the pods that will be running JupyterHub.
    Note the various sizes being picked. It's important that the right sizes be picked here as changing them will be more difficult later. 
    Having the master run as t2.micro is fine. The node size needs to be big enough to handle multiple Jupyter notebooks/pods/users running.
    The volume sizes are per pod which is really per user. We will pick nodes with t2.large with 10 GB volumes. 
    About 8 volumes can be attached to a node. So for 30 users, 5 nodes should be plenty.
    
    _Warning:_ Note that some EC2 instance types might have bad volume types: https://github.com/jupyterhub/zero-to-jupyterhub-k8s/issues/870#issuecomment-416712718
    
    ```bash
    kops create cluster $NAME \
        --zones $ZONES \
        --authorization RBAC \
        --master-size t2.micro \
        --master-volume-size 10 \
        --node-size t2.large \
        --node-volume-size 10 \
        --node-count 4 \
        --yes
    ```
    
    __There are options to create a private subnet within AWS and encrypt volumes. We are not going to do this. But the docs do state how if interested.__
    
    _Tip:_ To delete the cluster, `kops delete cluster $NAME --yes` 
    
9. Wait and check for the k8s cluster to be setup. There are various AWS resources being created and it takes time. 

    `kops validate cluster`
    
    To list all the resources created (_note the lack of --yes_): 
    
    ```bash
    kops delete cluster $NAME
    ```

10. Get the kubectl config needed to interact with the cluster

    `kops export kubecfg`

    Copy the config at _~/.kube/config_ to the corresponding location on your local machine. 

11. Install `kubectl` on your local machine. Kubectl will also be used Helm later and so needs to be installed locally.

    It also might be beneficial to install `kubectl` on the cluster master. Some of the more advance `kops` options use `kubectl`. https://github.com/kubernetes/kops/blob/master/docs/install.md

12. Enable dynamic storage on the k8s cluster. This will allow JupyterHub to give each user their own unique storage volumes.

    The docs have a different config file given. But that breaks. The following was found at https://github.com/helm/charts/issues/5188. 
    On your local machine, create a `storageclass.yml`. This assumes that the zones are the same as `ZONES` above.
    
    ```yaml
    kind: StorageClass
    apiVersion: storage.k8s.io/v1
    metadata:
      name: standard
    provisioner: kubernetes.io/aws-ebs
    parameters:
      type: gp2
      zones: ...
    ```

    Apply the changes: `kubectl apply -f storageclass.yml`

The cluster should be ready now.

###Install Helm 

https://z2jh.jupyter.org/en/latest/setup-helm.html

`Helm` is a package manager for k8s. It will be used to install and update JupyterHub with the k8s cluster. Helm is the name of the local command-line client. Tiller is the server-side executor that interacts with Helm.

1. Install Helm on your local machine.

    `curl https://raw.githubusercontent.com/kubernetes/helm/master/scripts/get | bash`
    
2. Create a Service Account in the cluster, initalize and secure Helm and Tiller. 

    Helm uses kubectl to interact with the k8s cluster. Make sure that the wanted k8s cluster is being used, i.e. that the right kubectl config is being used.

    ```bash
    kubectl --namespace kube-system create serviceaccount tiller
    kubectl create clusterrolebinding tiller --clusterrole cluster-admin --serviceaccount=kube-system:tiller
    helm init --service-account tiller --wait
    ```
    
3. Ensure that tiller is secure from access inside the cluster

    ```bash
    kubectl patch deployment tiller-deploy --namespace=kube-system --type=json --patch='[{"op": "add", "path": "/spec/template/spec/containers/0/command", "value": ["/tiller", "--listen=localhost:44134"]}]'
    ```
    
4. Verify

    The helm and tiller versions should be the same
    
    `helm version`
 
 ###Setup JupyterHub
 
 Most of the configuration work has already been done with Helm charts. However, there is some specific things that ned to still be done.
 
1.  Get the JupyterHub Helm repo
 
    ```bash 
    helm repo add jupyterhub https://jupyterhub.github.io/helm-chart/
    helm repo update
    ```
 
    This chart contains all of the minimal code to start a Jupyter Hub, manage the user nodes, and basic security. 
    
    To establish a proxy for JupyterHub, we need a key hash: `openssl rand -hex 32`
    
    On your local computer, create a yaml config file `config.yaml` and within it add:
    
    ```yaml
    proxy:
        secretToken: <The key hash derived above>
    auth:
      admin:
        users:
          - <list of users that will be JupyterHub admins>
      dummy:
        password: <unicode string that will be a shared password among users>
    ```
    
    This basic config will allow anyone to sign into JupyterHub with basic notebook creation rights, using the designated password. Admins listed will have the power to start and stop notebook servers of others.
  
2.  Install the chart into the k8s cluster from your local machine.
  
     ```bash
     # Suggested values: advanced users of Kubernetes and Helm should feel
     # free to use different values.
     RELEASE=jhub
     NAMESPACE=jhub

     helm upgrade --install $RELEASE jupyterhub/jupyterhub \
        --namespace $NAMESPACE  \
        --version 0.7.0 \
        --values config.yaml
     ```
     
     The version number 0.7.0 is the Helm version. The JupyterHub version matches accordingly to https://github.com/jupyterhub/helm-chart#versions-coupled-to-each-chart-release.
     
3.  Wait for the pods in the cluster to spin up. 
 
    `kubectl get pod --namespace jhub`
    
    Wait till pods `hub` and `proxy` are in a `ready` state.
    
4.  Get the public IP to sign into JupyterHub
 
    `kubectl describe service proxy-public --namespace jhub`
    
    The ip is found under `LoadBalancer Ingress`. 

5.  Open the ip in a browser and play.

    Note that when initially logging in as an user, the volume for that user hasn't been created yet. There will be a self-correcting error displayed that will go away once the volume is formed and attached.

###To delete everything

1. Delete the Helm Release

    On your local machine, `helm delete <YOUR-HELM-RELEASE-NAME> --purge`. Assume that `jhub` is the release name though it can be found via `helm list`.

2. Delete the k8s resources (not the actual k8s cluster).
    
    On your local machine, `kubectl delete namespace jhub`. (Assuming that `jhub` is the k8s namespace used.)
    
3. Delete the k8s cluster

    On the cluster master EC2 (created in _Install the k8s cluster in AWS_), `kops delete cluster asf-jupyter-cluster.k8s.local --yes`
    
    It will take a while to delete all the resources. It would be wise to double check that there is nothing orphaned.

4. Delete the cluster master EC2.

