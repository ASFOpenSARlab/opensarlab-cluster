
1. Create a role for EKS

1. Create a VPC for the cluster
    Follow _Create your Amazon EKS Cluster VPC_ in https://docs.aws.amazon.com/eks/latest/userguide/getting-started.html

1. Create cluster

    Some parameters:
    ```bash
    export EKS_CLUSTER_NAME=jupyter-dev
    export EKS_ROLE_ARN=arn:aws:iam::553778890976:role/jupyter-eks
    ```

    ```bash
    # Creating the cluster on the command line avoids possible issues later
    aws eks create-cluster \
        --name $EKS_CLUSTER_NAME \
        --role-arn $EKS_ROLE_ARN \
        --resources-vpc-config subnetIds=subnet-0045e5b992d9afe35,subnet-0d7ed44f212844dfe,securityGroupIds=sg-0e0c12237a49fccaf

    aws eks wait cluster-active --name $EKS_CLUSTER_NAME

    aws eks update-kubeconfig --name $EKS_CLUSTER_NAME --role-arn=$EKS_ROLE_ARN
    ```

    To use kubectl with EKS, we will be using AWS IAM Authenticator
    https://github.com/kubernetes-sigs/aws-iam-authenticator/blob/master/README.md

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

    To check that kubectl can get to theh EKS cluster, `aws get svc` should give the cluster name.

    Setup