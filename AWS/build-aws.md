This is largely taken from https://z2jh.jupyter.org/en/latest/amazon/step-zero-aws.html and https://kubernetes.io/docs/setup/custom-cloud/kops/
To simplify AWS management, a subaccount was created in AWS called JupyterHub that contains only the following.

### Install the k8s cluster master in AWS

This EC2 will be used to build and update the k8s clusters. Only one master needs to be built; mulitple clusters can be created via one master.

1. Create a IAM Role for the cluster

    Name: `jupyterhub-cluster`
    - AmazonEC2FullAccess
    - IAMFullAccess
    - AmazonS3FullAccess
    - AmazonVPCFullAccess
    - Route53FullAccess (Optional. This is useful later for url routing if wanted)

1. Create a Ec2 instance that will be the cluster master

    - type: AWS Linux
    - size: t2.micro
    - IAM role: jupyterhub-cluster
    - keypair: Create a new pair and save on your local machine

    On creation, note the public ip.

1. SSH into the cluster master
    
    `ssh -i my-key.pem ec2-user@cluster-master-public-ip`

1. Install `kops` on the cluster master. https://github.com/kubernetes/kops/blob/master/docs/install.md

    ```
    curl -Lo kops https://github.com/kubernetes/kops/releases/download/$(curl -s https://api.github.com/repos/kubernetes/kops/releases/latest | grep tag_name | cut -d '"' -f 4)/kops-linux-amd64
    chmod +x ./kops
    sudo mv ./kops /usr/local/bin/
    ```
    To check installation, type `kops` on the command line.

    We are keeping kops only on the cluster master for security reasons. any changes to the cluster will need to be done only within the ec2.

1. Create a keypair to be used by the cluster and other AWS resources

    `ssh-keygen`
    
    Skip the name and passphrase. Save in the rsa public default.

1. Manually create s3 bucket named `asf-jupyter-cluster` (or something similar. Remember that it has to be globally unique.)

    This bucket will contain cluster metadata used by kops. The docs recommmend that versioning be turned on.

### Create a k8s cluster

Different clusters can be created and managed from the previously made cluster master.

__Pro Tip:__ Use the command `kops get clusters` to see all the clusters currently built.

1. Within the cluster master, create some enviroment varibles: cluster name, bucket name, region, and AZs.

    The biggest difference between clusters is the _NAME_ and _KOPS_STATE_STORE_. These enviromental variables will need to be re-added whenever logging into the cluster master or switching to another cluster.

    ```bash
    export NAME=jupyter.k8s.local
    export KOPS_STATE_STORE=s3://asf-jupyter-cluster
    export REGION=`curl -s http://169.254.169.254/latest/dynamic/instance-identity/document|grep region|awk -F\" '{print $4}'` 
    #export ZONES=$(aws ec2 describe-availability-zones --region $REGION | grep ZoneName | awk '{print $2}' | tr -d '"')
    #export ZONES=$(echo $ZONES | tr -d " " | rev | cut -c 2- | rev)
    export ZONES=us-east-1a
    ```
    The reason we are doing one zone only is because of the issue with EBS volumes mismatching zones with the EC2s. There is a fix in the latest version of K8s but kops is not quite there yet.

1. Create k8s cluster.

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
        --master-size m4.xlarge \
        --master-volume-size 30 \
        --node-size m5.xlarge \
        --node-volume-size 10 \
        --node-count 4 \
        --yes
    ```
    
    __There are options to create a private subnet within AWS and encrypt volumes. We are not going to do this. But the docs do state how if interested.__
    
    __Pro Tip:__ To delete the cluster, `kops delete cluster $NAME --yes`

    Clusters can be updated in place (https://kubernetes.io/docs/setup/custom-cloud/kops/) but to do so takes a long time and could create instablilties. Thus do so under the most distressful circumstances.
    
1. Wait and check for the k8s cluster to be setup. There are various AWS resources being created and it takes time. 

    `kops validate cluster`
    
    To list all the resources created (_note the lack of --yes_): 
    
    ```bash
    kops delete cluster $NAME
    ```

1. Get the kubectl config needed to interact with the cluster

    `kops export kubecfg`

    Copy the config at _~/.kube/config_ to the corresponding location on your local machine.

    Since this config is dependent on the cluster specifics, it's recommended that the config be renamed (e.g. `config.jupyter`) as to avoid being overwritten.

1. Install `kubectl` on your local machine. Kubectl will also be used Helm later and so needs to be installed locally.

    It also might be beneficial to install `kubectl` on the cluster master. Some of the more advance `kops` options use `kubectl`. https://github.com/kubernetes/kops/blob/master/docs/install.md

1. Enable dynamic storage on the k8s cluster. This will allow JupyterHub to give each user their own unique storage volumes.

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

### Add Other Needed AWS Resources

Data that is too big to hold in the notebook images will need to be stored in a s3 bucket that is readonly for users. We will create an user and role that grants access for the users.

1. Create s3 bucket to hold common data: `asf-jupyter-data` (or something else globally unique)

1. Create an user to hold the access keys for aws cli

    - User name: _Read_asf_jupyter_data_only_
    - Access type: _Programmatic Access_
    - The notebook users should only be able to only read from only the one bucket. Any other operations are prohibited. 
    - Create a policy like below and attach to the user. Modify the bucjet name as needed.
    
    ```config
    {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:ListBucketMultipartUploads",
                "s3:GetObject"
            ],
            "Resource": [
                "arn:aws:s3:::asf-jupyter-data",
                "arn:aws:s3:::asf-jupyter-data/*"
            ]
        }
    ]
    }
    ```
    - Save the secret access key info somewhere for later.

1. Create a ECR repo to hold the custom images used by the notebooks

    This ensures that any images used can be used within AWS.
    
    - Within AWS ECR, click on `Create Repository`. This is where the images with tags are held. So name the repo the name of the image being held. (It's confusing, I know.)
    - When building images, try to `--squash` them to reduce size. The Notebook images can get big.

### Install Helm 

https://z2jh.jupyter.org/en/latest/setup-helm.html

`Helm` is a package manager for k8s. It will be used to install and update JupyterHub with the k8s cluster. Helm is the name of the local command-line client. Tiller is the server-side executor that interacts with Helm.

1. Install Helm on your local machine.

    `curl https://raw.githubusercontent.com/kubernetes/helm/master/scripts/get | bash`
    
1. Create a Service Account in the cluster, initalize and secure Helm and Tiller. 

    Helm uses kubectl to interact with the k8s cluster. Make sure that the wanted k8s cluster is being used, i.e. that the right kubectl config is being used.

    ```bash
    kubectl --namespace kube-system create serviceaccount tiller
    kubectl create clusterrolebinding tiller --clusterrole cluster-admin --serviceaccount=kube-system:tiller
    helm init --service-account tiller --wait
    ```
    
1. Ensure that tiller is secure from access inside the cluster

    ```bash
    kubectl patch deployment tiller-deploy --namespace=kube-system --type=json --patch='[{"op": "add", "path": "/spec/template/spec/containers/0/command", "value": ["/tiller", "--listen=localhost:44134"]}]'
    ```
    
1. Verify

    The helm and tiller versions should be the same.
    It critical that if the k8s version is updated that helm and tiller versions also match. Otherwise, the cluster might become unstable.
    
    `helm version`
 
 ### Setup JupyterHub
 
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
    # This helm config file modifies the defaults found in zero-to-jupyterhub-k8s/jupyterhub/
    # Possible values are scattered throughout the doc starting at https://z2jh.jupyter.org/en/latest/setup-jupyterhub.html

    # Proxy token can be recreated via `openssl rand -hex 32`. This token isn't really used anywhere else so I'm not sure of the security concerns.
    proxy:
      secretToken: <token>

    auth:
      admin:
        users:
          - user1
          - user2

      whitelist:
        users:
          - user1
          - user2

      dummy:
        password: <pass>  # This password will be shared among all users.

    singleuser:
      image:
        name: 553778890976.dkr.ecr.us-east-1.amazonaws.com/asf-franz-labs
        tag: build.9
      extraEnv:
        # Keys needed for the notebook servers to talk to s3
        AWS_ACCESS_KEY_ID: "AKIAJKMUJ4GJWSDOUQSA"
        AWS_SECRET_ACCESS_KEY: "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"
      lifecycleHooks:
        postStart:
          exec:
            # When the jupyterhub server mounts the EBS volumes to $HOME, it "deletes" anything in that directory.
            # The volumes cannot be mounted anywhere else.
            # Thus hidden directories for condas and other programs when originally built will get destroyed.
            # This hook takes copies of those files (safely moved during the image build) and copies them back to $HOME.
            command: ["rsync", "-a", "-v", "--ignore-existing", "/home/commons/.", "/home/jovyan/"]

    # Always pull the latest image when the Helm chart is updated
    prePuller:
      continuous:
        enabled: true
      hook:
         enabled: true
    ```
    
    This basic config will allow anyone whitelisted to sign into JupyterHub with basic notebook creation rights, using the designated password. Admins listed will have the power to start and stop notebook servers of others.
  
1.  Install the chart into the k8s cluster from your local machine.

    It's suggested that the _RELEASE_ and _NAMESPACE_ match the basic name of the cluster in some fashion. This wil reduce confusion when multiple clusters are used.
  
     ```bash
     # Suggested values: advanced users of Kubernetes and Helm should feel
     # free to use different values.
     RELEASE=jupyter
     NAMESPACE=jupyter

     helm upgrade --install $RELEASE jupyterhub/jupyterhub \
        --namespace $NAMESPACE  \
        --version 0.7.0 \
        --values config.yaml
     ```
     
     The version number 0.7.0 is the Helm version. The JupyterHub version matches accordingly to https://github.com/jupyterhub/helm-chart#versions-coupled-to-each-chart-release.
     
1.  Wait for the pods in the cluster to spin up. 
 
    `kubectl get pod --namespace jupyter`
    
    Wait till pods `hub` and `proxy` are in a `ready` state.
    
1.  Get the public IP to sign into JupyterHub
 
    `kubectl describe service proxy-public --namespace jupyter`
    
    The ip is found under `LoadBalancer Ingress`. 

1.  Open the ip in a browser and play.

    Note that when initially logging in as an user, the volume for that user hasn't been created yet. There will be a self-correcting error displayed that will go away once the volume is formed and attached.

### To delete everything

1. Delete the Helm Release

    On your local machine, `helm delete jupyter --purge`. Assume that `jupyter` is the release name though it can be found via `helm list`.

1. Delete the k8s resources (not the actual k8s cluster).
    
    On your local machine, `kubectl delete namespace jupyter`. (Assuming that `jupyter` is the k8s namespace used.)
    
1. Delete the k8s cluster

    On the cluster master EC2 (created in _Install the k8s cluster in AWS_), `kops delete cluster asf-jupyter-cluster.k8s.local --yes`
    
    It will take a while to delete all the resources. It would be wise to double check that there is nothing orphaned.

1. Delete the cluster master EC2.
