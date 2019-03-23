# ASF Jupyter Hub

Thee are three ways to install Jupyter Hub in AWS:

1. [Setup using CodePipeline and CloudFormation](#installation-of-jupyterhub-with-codepipeline)
1. [Setup using manual installation of CloudFormation](#manual-installation-of-jupyterhub-using-cloudformation)
1. Use the docs in the [_archive_](https://github.com/asfadmin/asf-jupyter-hub/tree/archive) branch


## Installation of JupyterHub with CodePipeline

In general, the following will be performed:

1. Create an User Role (jupyter-hub-build)
1. Create a Build Pipeline 
1. Add build step to pipeline and rerun

### Create an User Role

An AWS service role is needed to manage the Code Pipeline. The actual name can be decided by the user. In this case, we will use _jupyter-hub-build_. Multiple clusters can use this role.

We will be creating a custom role. Within IAM, create a _Role_ by doing the following: 

1. AWS Service for EKS
1. Name the role _jupyter-hub-build_
1. Click through everything else and create.
1. Click on the brand-new role.
1. Within _Permissions_, delete the EKS policies.
1. Add to the inline policy the following JSON:

    ```json
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "ec2:*",
                    "logs:*",
                    "s3:*",
                    "iam:*",
                    "eks:*",
                    "autoscaling:*",
                    "elasticloadbalancing:*",
                    "codebuild:*",
                    "cloudformation:*"
                ],
                "Resource": "*"
            }
        ]
    }
    ```

1. Within _Trust Relationships_ add

    - codepipeline
    - cloudformation
    - codebuild
    - (Optional) Any user role ARN. This will allow users to interact with cluster via AWS.

### Create a Build Pipeline

Go to https://console.aws.amazon.com/codesuite/codepipeline/pipelines. 

Create a new pipeline 

- __Pipeline name__: anything you want
- __Existing service role__: _jupyter-hub-build_
- __Default Location__ for the S3 bucket works though a custom location might have some benefits.
- __Source provider__: GitHub. 
    - Opt-in to connect
    - Pick repo _asf\_jupyter\_hub_
    - Choose the proper branch (most likely _prod_)
    - Use GitHub webhooks
- Skip the __Build stage__
- Deploy an AWS CloudFormation template
    - US East
    - Create or Update Stack
    - __Stack Name__: Use a meaningful unique name. Otherwise, an existing stack will get clobbered. Also, all resources created by the cloudformation template will be prepended by this name.
    - __Template__: `SourceArtifact::cloudformation.yaml`
    - __Template configuration__: _skip_
    - __Capabilities__: `CAPABILITY_NAMED_IAM`
    - __Role Name__: `jupyter-hub-build`
    - Advanced: 
        - __Output file name__: _skip_
        - __Parameter overrides__ as described below

The parameter overrides for the cloudformation template can be the following:

* __CertificateArn__ (required). The ARN of the SSL certificate used by the load balancer (e.g.  arn:aws:acm:us-east-1:553778890976:certificate/862ecb20-8df6-458a-b45d-bc03b9b02af5).
* __VpcId__ (required). Within the AWS main menu, select _VPC_. Get the default VPC ID from within _Your VPCs_ (e.g. vpc-4da21e37).  
* __Subnets__ (required). Within the AWS main menu, select _VPC_. Choose any number of _Subnet ID_s from within _Subnets_ (e.g. subnet-39a09073,subnet-4388e824).
* __CodeBuildServiceRoleArn__ (required). The service role created eariler (e.g. _jupyter-hub-build_). 
* __AdminUserName__ (required). The name of the initial Jupyter Hub admin who is also the only one initially whitelisted. Without this admin, no one else can be added as an Jupyter Hub user.
* __AppPassword__ (required). The common Jupyter Hub login password used by all users.
* __ImageTag__ (required). The build tag of the jupyter notebook docker image.
* __ImageName__. The jupyter notebook docker image. While not required, it's better to use ECR.
* __NodeImageId__. The AMI id for the node instances.
* __NodeInstanceType__. EC2 instance type for the node instances (e.g. m5.xlarge). 
* __NodeAutoScalingGroupMinSize__. Minimum size of Node Group ASG (e.g. 1).
* __NodeAutoScalingGroupMaxSize__. Maximum size of Node Group ASG. Set to at least 1 greater than NodeAutoScalingGroupDesiredCapacity (e.g. 4).
* __NodeAutoScalingGroupDesiredCapacity__. Desired capacity of Node Group ASG (e.g. 2).
* __NodeVolumeSize__. Node volume size in GB (e.g. 100).
* __NodeAccessKeyId__. AWS CLI access key ID used within jupyter notebook servers to perform AWS services like reading from S3. One can create the key from security credentials attached to an IAM User with the proper policy.
* __NodeSecretKey__. AWS CLI secret key ID used within jupyter notebook servers to perform AWS services like reading from S3.
* __LoadBalancerCidrBlock__. Firewall to the load balancer. This doesn't affect the whole cluster.
* __NodeProxyPort__. The hub proxy port open to the load balancer.

They need to be in JSON format like:

```json
{
    "CertificateArn":" arn:aws:acm:us-east-1:553778890976:certificate/862ecb20-8df6-458a-b45d-bc03b9b02af5", 
    "VpcId":"vpc-4da21e37", 
    "Subnets":"subnet-39a09073,subnet-4388e824",
    "CodeBuildServiceRoleArn":"jupyter-hub-build",
    "AdminUserName":"admin",
    "AppPassword":"admin",
    "ImageTag":"build.23"
}
```

After entering in the parameter overrides, click and review and then __Create__.  

And then wait. 

### Add build step to Pipeline and rerun

In the initial creation of the Code Pipeline, a build step was not given. This is intentional. Only after the CloudFormation template is initially built will the Code Build project exist. Thus the build step will need to be added afterwards and the pipeline reran.

Once the full pipeline (including the Code Build parts) has been successfully built, future pipeline runs will be able to run the pipeline as it . 

To add Code Build, click on the just created pipeline in the console.

Click __Edit__ at the top of the main flowchart.

Click __Add Stage__ at the bottom after _Deploy_ and name it _build_.

Click __Action Group__ within the following: 

 - __Action Name__: _build_
 - __Action Provider__: _AWS CodeBuild_
 - __Input artifacts__: _SourceArtifact_
 - __Project name__: The stack name
 - __Output artifacts__: skip

 Click save, save, save
 Click __Release Change__

If there is a build error with Tiller failing, then retry.

If all goes well, everything will be green and you will have a working cluster.

Don't forget to grab load balancer URL from CloudFormation Outputs.


### Manage cluster locally (under development)

While not needed to setup the cluster, _kubectl_ can be useful in monitoring the health of the cluster and making manual changes (doing so with a heap of caution).

1. Setup kubectl

    It's assumed that kubectl is setup already. If not, follow https://kubernetes.io/docs/tasks/tools/install-kubectl/.

1. Setup aws-cli

    It's assumed that aws-cli is setup already. If not, follow https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html

1. Setup aws-iam-authenticator

    The _aws-iam-authenticator_ is "a tool to use AWS IAM credentials to authenticate to a Kubernetes cluster".
    This makes it far easier to manage EKS from a local machine.

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

Once kubectl, aws-cli, and the authenticator is installed properly, we can check what EKS clusters are active via `aws eks list-clusters`.

If the cluster that we want is active we can get the _kubeconfig_ file to interact with the cluster.

Note: the _kubeconfig_ file is appended and not overwritten. 

```bash
# You need to run against the root account and not a sub-account
# Users will need to be added as Trusted to the _jupyter-hub-build_ role for this to work.
STS_DICT=$(aws sts assume-role --role-arn arn:aws:iam::553778890976:role/jupyter-hub-build --role-session-name ARandomSessionNameYouPickHere --profile=us-east-1)

export AWS_ACCESS_KEY_ID=$(python -c "print($STS_DICT['Credentials']['AccessKeyId'])")
export AWS_SECRET_ACCESS_KEY=$(python -c "print($STS_DICT['Credentials']['SecretAccessKey'])")
export AWS_SESSION_TOKEN=$(python -c "print($STS_DICT['Credentials']['SessionToken'])")

aws eks update-kubeconfig --name $EKS_CLUSTER_NAME

# Check to see if the update was successful
kubectl get svc
```
You can now do full `kubectl` commands against the cluster for a short period of time (about one hour).

## Manual installation of JupyterHub using CloudFormation (not recommended)

These are the steps to create a JupyterHub instance running in a Kubernetes cluster via AWS's EKS.

### Install Prerequisites

1. Setup kubectl

    It's assumed that kubectl is setup already. If not, follow https://kubernetes.io/docs/tasks/tools/install-kubectl/

1. Setup aws-cli

    It's assumed that aws-cli is setup already. If not, follow https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html

1. Setup aws-iam-authenticator

    The _aws-iam-authenticator_ is "a tool to use AWS IAM credentials to authenticate to a Kubernetes cluster".
    This makes it far easier to manage EKS from a local machine.

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

### Deploy the EKS Cluster

1. Deploy the Cloudformation template

    Start the default cloudformation config deployment - adding the `stack-name`. The default values are listed in the template's Parameter section.

    >JupyterHub uses a proxy to manage traffic within the jupyter setup.
    >The hub proxy is ran within a pod (with accompying service) which is within one of the EC2 nodes running within the cluster.
    >If more than one non-system namespace is running on that node, then there will be more than one proxy service also running on that node.
    >The EC2 node uses various ports to communicate with the various parts of the cluster and with the external facing load balancer.
    >Using more than one hub proxy service will cause conflicts with ports leading to unexpected beahvior among the namespaces.
    >Therefore it is recommended that only one non-system namespace be ran within the kubernetes cluster.
    >If this is not reasonable, then the default NodeProxyPort must be overridden manually within the proper pipeline.
    >While this series of events will be rare, it's worth noting to avoid future headaches.

    ```
    aws cloudformation deploy --stack-name jupyter-dev --template-file cloudformation.yaml --capabilities CAPABILITY_NAMED_IAM
    ```

    To override any of the parameters, add the `--parameter-overrides` option the command.

    Example:

    ```
    aws cloudformation deploy --stack-name jupyter-dev \
                              --template-file cloudformation.yaml \
                              --capabilities CAPABILITY_NAMED_IAM \
                              --parameter-overrides VpcId=vpc-4da21e37 \
                                                    Subnets=subnet-39a09073,subnet-4388e824,subnet-68a1fb67 \
                                                    CertificateArn=arn:aws:acm:us-east-1:553778890976:certificate/862ecb20-8df6-458a-b45d-bc03b9b02af5 \
                                                    NodeProxyPort=30052
    ```

    Setup will take quite a few minutes.
    During the build `aws cloudformation describe-stacks --stack-name jupyter-eml --query 'Stacks[0].StackStatus'` will return the status.

1. Kubectl config

    Once setup is complete, let's update the kubeconfig on the local machine so that we can talk with the cluster.
    Note that usually this appends to new credentials to the file.

    **Note: DO NOT use the `--role-arn` option. Doing so will cause a mass of headaches.** Using assumed roles for AWS access can cause issues with local kubectl.
    Even though the cluster was created by a particular user, authentication will use AWS credentials which might not match.
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

    Modify _<ARN of instance role (not instance profile)>_ with the **NodeInstanceRole** from CloudFormation _Outputs_.

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

    The cluster should be fully setup. Check by doing a `kubectl get all --all-namespaces -owide`.
    The number of nodes listed should equal the number of EC2s.
    However, no load balancers should exist. That will be deployed later.

### Install JupyterHub

Follow along at https://z2jh.jupyter.org/en/latest/setup-helm.html

The Helm GitHub repo is

We wil be using Helm to manage installation. `Helm` is a package manager for k8s. It will be used to install and update JupyterHub with the k8s cluster.
Helm is the name of the local command-line client. Tiller is the server-side executor that interacts with Helm.

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

    To establish a proxy for JupyterHub, we need a key hash: `openssl rand -hex 32`. This will go under proxy.secretToken.

    The proxy.service.nodePorts.http value must match the nodePorts from the cloudformation.

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
                http: 30052

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

    This basic config will allow anyone whitelisted to sign into JupyterHub with basic notebook creation rights, using the designated password.
    Admins listed will have the power to start and stop notebook servers of others.

1.  Install the chart into the k8s cluster from your local machine.

    It's suggested that the _RELEASE_ and _NAMESPACE_ match the basic name of the cluster in some fashion.
    This wil reduce confusion when multiple clusters are used.

    **Make sure that the right config file is picked aws well as the namespace. Otherwise grave consequences will follow.**

     ```bash
     # Suggested values: advanced users of Kubernetes and Helm should feel
     # free to use different values.
     RELEASE=dev; NAMESPACE=dev; helm upgrade --install $RELEASE jupyterhub/jupyterhub --namespace $NAMESPACE  --version 0.8.0  --values config.yaml
     ```

     The version number 0.8.0 is the Helm version.
     The JupyterHub version matches accordingly to https://github.com/jupyterhub/helm-chart#versions-coupled-to-each-chart-release.

1.  Wait for the pods in the cluster to spin up.

    `kubectl get pod --namespace jupyter`

    Wait till pods `hub` and `proxy` are in a `ready` state.

###  Open the ip in a browser and play.

>If the connection hangs or there is a 502 Gateway error, most likely the ports and/or security groups are not properly configured.

>Note that when initially logging in as an user, the volume for that user hasn't been created yet.
>There will be a self-correcting error displayed that will go away once the volume is formed and attached.

### To delete everything

1. Delete the Helm Release resources

    On your local machine, `helm delete $RELEASE --purge`. The release name though it can be found via `helm list`.

    This will delete most of the resources in the accompying namespace. It's possible that active user pods will be orphaned.
    However, if the cluster is rebuilt within the same namespace, the active user pod will be reassigned into the new cluster setup. The pod won't be lost.

1. Delete the k8s resources (not the actual k8s cluster).

    On your local machine, `kubectl delete namespace $NAMESPACE`.

    Unlike deleting a Helm Release which may or may not delete all resources in the particular namespace, this command will delete everything. So be extra careful.

1. Delete the k8s cluster via cloudformation.

    `aws cloudformation delete-stack --stack-name $STACK_NAME`

    It will take a while to delete all the resources. It would be wise to double check that there is nothing orphaned afterwards.
