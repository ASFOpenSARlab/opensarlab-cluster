
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

    aws eks wait cluster-active --name $EKS_CLUSTER_NAME

    aws eks update-kubeconfig --name $EKS_CLUSTER_NAME --role-arn=$EKS_ROLE_ARN
    ```
    Note the output during setup. Check that values are correct. Setup can take up to 10 minutes. To check on the status of the cluster, `aws eks -describe-cluster --name $EKS_CLUSTER_NAME --query cluster.status`

1. Fix some broken parts

    Using assumed roles for AWS access can cause issues with local kubectl. Even though the cluster was created by a particular user, authentication will use AWS credentials which might not match.
    Within kubeconfig replace the section

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

    with (subsitute the proper AWS config profile)

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
               value: "default"
    ```

    To check that kubectl can get to the EKS cluster, `aws get svc` should give the cluster name.

1. Add worker nodes

    By this point in the setup there should be a K8s cluster running in AWS including a couple of EC2s, a system of VPCs, Role Names, etc.

    Open CloudFormation https://console.aws.amazon.com/cloudformation/

    Create a Stack with the following:

     - Specify an Amazon S3 template URL: https://amazon-eks.s3-us-west-2.amazonaws.com/cloudformation/2019-02-11/amazon-eks-nodegroup.yaml
     - StackName: jupyter-dev-worker-nodes
     - ClusterName: jupyter-dev
     - ClusterControlPlaneSecurityGroup: The security group gotten in _Create a VPC for the cluster_ above.
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

    The cluster should be fully setup. Check by doing a `kubectl get all --all-namespaces`

1. Install JupyterHub

    ...
