
### EKS Cluster
1. Create a role for EKS

    Within https://console.aws.amazon.com/iam, create a role with the following:

    - AWS Service: EKS
    - Policies: (default) AmazonEKSClusterPolicy, (default) AmazonEKSServicePolicy
    - Role Name: jupyter-eks
    - Trust Relationship: eks.amazonaws.com

1. Create a VPC for the cluster

    (The following largely follows _Create your Amazon EKS Cluster VPC_ in https://docs.aws.amazon.com/eks/latest/userguide/getting-started.html)

    Open CloudFormation https://console.aws.amazon.com/cloudformation

    Click _Create Stack_

    Within _Specify an Amazon S3 template URL_ enter https://amazon-eks.s3-us-west-2.amazonaws.com/cloudformation/2019-02-11/amazon-eks-vpc-sample.yaml

    Specfify name: _eks-vpc_. Use default subnet values.

    Hit **Create**

    After creation of the stack, within _Outputs_ remember the __SecurityGroups__, __VpcId__, and __SubnetIds__.

1. Setup kubectl, aws-cli and aws-iam-authenticator

    It's assumed that kubectl is setup already. If not, follow https://kubernetes.io/docs/tasks/tools/install-kubectl/

    It's assumed that aws-cli is setup already. If not, follow https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html

    _aws-iam-authenticator_ is "a tool to use AWS IAM credentials to authenticate to a Kubernetes cluster". This makes it far easier to manage EKS from a local machine.

    Download and install aws-iam-authenticator:

    Choose the url that matches your OS

    - Linux: https://amazon-eks.s3-us-west-2.amazonaws.com/1.11.5/2018-12-06/bin/linux/amd64/aws-iam-authenticator

    - MacOS: https://amazon-eks.s3-us-west-2.amazonaws.com/1.11.5/2018-12-06/bin/darwin/amd64/aws-iam-authenticator

    - Windows: https://amazon-eks.s3-us-west-2.amazonaws.com/1.11.5/2018-12-06/bin/windows/amd64/aws-iam-authenticator.exe

    Run the following commands:

    ```bash
    curl -o aws-iam-authenticator <url from above>

    chmod +x ./aws-iam-authenticator

    # They recommend that the authentictor be placed in a easy location for the PATH.
    cp ./aws-iam-authenticator $HOME/bin/aws-iam-authenticator && export PATH=$HOME/bin:$PATH

    # Add to home PATH
    echo 'export PATH=$HOME/bin:$PATH' >> ~/.bashrc

    # Test to see if it works
    aws-iam-authenticator help
    ```

1. Create cluster

    Some parameters decided in previous steps. The values will most likely be different that what is listed here.

    ```bash
    export EKS_CLUSTER_NAME=jupyter-dev
    export EKS_ROLE_ARN=arn:aws:iam::553778890976:role/jupyter-eks
    ```

    Using the AWS UI may seem simpler, but in experimenting with the setup I have found that creating the cluster on the command line avoids possible issues later.

    ```bash
    aws eks create-cluster \
        --name $EKS_CLUSTER_NAME \
        --role-arn $EKS_ROLE_ARN \
        --resources-vpc-config subnetIds=subnet-0045e5b992d9afe35,subnet-0d7ed44f212844dfe,securityGroupIds=sg-0e0c12237a49fccaf

    # Wait until clsuter is active
    aws eks wait cluster-active --name $EKS_CLUSTER_NAME
    ```
    Note the output during setup. Check that values are correct. Setup can take up to 10 minutes. To check on the status of the cluster, `aws eks describe-cluster --name $EKS_CLUSTER_NAME --query cluster.status`


1. Kubectl config

    Once setup is complete, let's update the kubeconfig on the local machine so that we can talk with the cluster. Note that usually this appends to new credentials to the file.

    **Note: DO NOT use the --role-arn option. Doing so will cause a mass of headaches.** Using assumed roles for AWS access can cause issues with local kubectl. Even though the cluster was created by a particular user, authentication will use AWS credentials which might not match.
    Within kubeconfig replace the section

    ```bash
    aws eks update-kubeconfig --name $EKS_CLUSTER_NAME

    # Check to see if the update was successful
    kubectl get svc
    ```

    Check the config. If it looks something like:

    ```yaml
    users:
    - name: arn:aws:eks:us-east-1:553778890976:cluster/jupyter-dev
      user:
        exec:
          apiVersion: client.authentication.k8s.io/v1alpha1
          args:
          - token
          - -i
          - jupyter-dev
          - -r
          - arn:arn:aws:iam::553778890976:role/jupyter-eks
          command: aws-iam-authenticator
    ```

    then change the config to (subsitute the proper AWS config profile)

    ```yaml
    users:
    - name: arn:aws:eks:us-east-1:553778890976:cluster/jupyter-dev
      user:
        exec:
          apiVersion: client.authentication.k8s.io/v1alpha1
          args:
          - token
          - -i
          - jupyter-dev
          command: aws-iam-authenticator
          env:
             - name: AWS_PROFILE
               value: "my_profile"
    ```

    To check that kubectl can get to the EKS cluster, `aws get svc` should give the cluster name.

1. Add worker nodes

    By this point in the setup there should be a K8s cluster running in AWS including
     - VPCs
     - Roles
     - Security Groups
     - Subnets
     - Basic Kubernetes cluster with certificate and credentials

    However, there should be no EC2s running that will support pods. For this to occur, worker nodes need to be set up.

    Open CloudFormation https://console.aws.amazon.com/cloudformation/

    Create a Stack with the following:

     - Specify an Amazon S3 template URL: https://amazon-eks.s3-us-west-2.amazonaws.com/cloudformation/2019-02-11/amazon-eks-nodegroup.yaml
     - StackName: jupyter-dev-worker-nodes
     - ClusterName: jupyter-dev
     - ClusterControlPlaneSecurityGroup: The security group gotten in _Create a VPC for the cluster_ above.
     - NodeGroupName: jupyter-dev
     - NodeInstanceType: m4.xlarge.  Note that this will need to be fine-tuned based on the needs of the cluster.
     - NodeImageId: ami-0eeeef929db40543c. This assumes that kubernetes 1.11 is being used.
     - BootstrapArguments: None for now. Though autoscaling will have values here in future development.
     - VpcId: The vpc id gotten in _Create a VPC for the cluster_ above.
     - Subnets: The subnets gotten in _Create a VPC for the cluster_ above.
     - For other values, pick what is best to your heart's content

    Choose **Create**

    Note **NodeInstanceRole** in _Outputs_. This will be used later.

    Apparently, nodes still need help in joining the cluster they are assigned to via kubectl.

    Download `curl -O https://amazon-eks.s3-us-west-2.amazonaws.com/cloudformation/2019-02-11/aws-auth-cm.yaml` (preferably somewhere nice)

    Modify _<ARN of instance role (not instance profile)>_ with the **NodeInstanceRole** from _Outputs_ as found in

    ```yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: aws-auth
      namespace: kube-system
    data:
      mapRoles: |
        - rolearn: <ARN of instance role (not instance profile)>
          username: system:node:{{EC2PrivateDNSName}}
          groups:
            - system:bootstrappers
            - system:nodes
    ```

    Apply changes and wait till changes are done:

    ```bash
    kubectl apply -f aws-auth-cm.yaml
    kubectl get nodes --watch
    ```

    The cluster should be fully setup. Check by doing a `kubectl get all --all-namespaces -owide`. The number of nodes listed should equal the number of EC2s. However, no load balancers should exist. That comes when Jupyterhub is set up.


### Install JupyterHub

Follow along at https://z2jh.jupyter.org/en/latest/setup-helm.html

We wil be using Helm to manage installation. `Helm` is a package manager for k8s. It will be used to install and update JupyterHub with the k8s cluster. Helm is the name of the local command-line client. Tiller is the server-side executor that interacts with Helm.

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
        AWS_ACCESS_KEY_ID: "AKIAJ**"
        AWS_SECRET_ACCESS_KEY: "***"
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

     helm upgrade --install $RELEASE jupyterhub/jupyterhub --namespace $NAMESPACE  --version 0.8.0  --values config.yaml
     ```

     The version number 0.8.0 is the Helm version. The JupyterHub version matches accordingly to https://github.com/jupyterhub/helm-chart#versions-coupled-to-each-chart-release.

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

