
### Deploy the EKS Cluster via Cloudformation
1. Deploy the Cloudformation template

    Review the stack parameters and determine whether any of the default values should be overridden for your particular deployment.

    ```
    aws cloudformation deploy --stack-name myStackName \
                              --template-file cloudformation.yaml \
                              --capabilities CAPABILITY_NAMED_IAM \
                              --parameter-overrides VpcId=myVpcId \
                                                    Subnets=mySubnetId1,mySubnetId2 \
                                                    CertificateArn=myCertificateArn \
                                                    NodeProxyPort=myProxyPort
    ```

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

1. Configure Kubernetes to find worker nodes

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

#### Pick a load balancer port number

We will be manually setting the ports that the proxy is listening for the balancer. The proxy is a pod (with service) within one of the EC2 nodes running within the cluster. If more than one non-system namespace is running on the node, then there might be more than one proxy service.

To see all the services, `kubectl get svc --all-namespaces`. If there are any _proxy_public_, make sure that any redirection ports chosen don't conflict. For instance, within `80:31855/TCP,443:31413/TCP`, we can't choose the port of 31855 or 31413.

Pick any number between 30000 - 40000 that doesn't conflict. Remember these. They will be added to the helm config later.


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
       https:
            enabled: false
       service:
            type: NodePort
            nodePorts:
                http: 31080

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
        tag: build.22
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
                command: ["gitpuller", "https://github.com/asfadmin/asf-jupyter-notebooks.git", "master", "notebooks"]

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

    **Make sure that the right config file is picked aws well as the namespace. Otherwise grave consequences will follow.**

     ```bash
     # Suggested values: advanced users of Kubernetes and Helm should feel
     # free to use different values.
     RELEASE=jupyter; NAMESPACE=jupyter; helm upgrade --install $RELEASE jupyterhub/jupyterhub --namespace $NAMESPACE  --version 0.8.0  --values config.yaml
     ```

     The version number 0.8.0 is the Helm version. The JupyterHub version matches accordingly to https://github.com/jupyterhub/helm-chart#versions-coupled-to-each-chart-release.

1.  Wait for the pods in the cluster to spin up.

    `kubectl get pod --namespace jupyter`

    Wait till pods `hub` and `proxy` are in a `ready` state.

###  Open the ip in a browser and play.

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
