# ASF Jupyter Hub

Thee are two ways to install Jupyter Hub in AWS:

1. Setup using CodePipeline and CloudFormation
1. Use the docs in the [_archive_](https://github.com/asfadmin/asf-jupyter-hub/tree/archive) branch


## Installation of JupyterHub with CodePipeline

In general, the following will be performed:

1. Create an User Role (_jupyter\-hub\-build_)
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

* __OAuthDnsName__ (required). DNS name used for Earthdata authentication.
* __OAuthClientId__ (required). Earthdata authentication client id.
* __OAuthClientSecret__ (required). Earthdata authentication client secret.
* __CertificateArn__ (required). The ARN of the SSL certificate used by the load balancer (e.g.  arn:aws:acm:us-east-1:553778890976:certificate/862ecb20-8df6-458a-b45d-bc03b9b02af5).
* __VpcId__ (required). Within the AWS main menu, select _VPC_. Get the default VPC ID from within _Your VPCs_ (e.g. vpc-4da21e37).  
* __Subnets__ (required). Within the AWS main menu, select _VPC_. Choose any number of _Subnet ID_s from within _Subnets_ (e.g. subnet-39a09073,subnet-4388e824).
* __CodeBuildServiceRoleArn__ (required). The service role created eariler (e.g. _jupyter-hub-build_).
* __AdminUserName__ (required). The name of the initial Jupyter Hub admin who is also the only one initially whitelisted. Without this admin, no one else can be added as an Jupyter Hub user.
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
* __NodeProxyPort__. The hub proxy port open to the load balancer. _This needs to be unique between the load balancer and the hub proxy._
* __Announcement__. Announcement text to be displayed on the sign-in page.

They need to be in JSON format like:

```json
{
    "CertificateArn":" arn:aws:acm:us-east-1:553778890976:certificate/862ecb20-8df6-458a-b45d-bc03b9b02af5",
    "VpcId":"vpc-4da21e37",
    "Subnets":"subnet-39a09073,subnet-4388e824",
    "CodeBuildServiceRoleArn":"jupyter-hub-build",
    "AdminUserName":"someEarthdataUser",
    "ImageTag":"build.23",
    "OAuthDnsName":"opensarlab-test.asf.alaska.edu",
    "OAuthClientId":"1QD_HXBUsZHQnlO9d7Lc6A",
    "OAuthClientSecret":"mySecret"
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

>If the connection hangs or there is a 502 Gateway error, most likely the ports and/or security groups are not properly configured.

>Note that when initially logging in as an user, the volume for that user hasn't been created yet.
>There will be a self-correcting error displayed that will go away once the volume is formed and attached.

### Manage cluster locally

While not needed to setup the cluster, _kubectl_ can be useful in monitoring the health of the cluster and making manual changes (doing so with a heap of caution).

1. Setup kubectl

    It's assumed that kubectl is setup already. If not, follow https://kubernetes.io/docs/tasks/tools/install-kubectl/.

1. Setup awscli>=1.16.158

    It's assumed that aws-cli is setup already. If not, follow https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html   

Once kubectl and aws-cli are installed properly, we can check what EKS clusters are active via `aws eks list-clusters`.

If the cluster that we want is active we can get the _kubeconfig_ file to interact with the cluster.

Note: the _kubeconfig_ file is appended and not overwritten.

Get credentials for a temporary session.

```bash
# You need to run against the root account and not a sub-account
# Users will need to be added as Trusted to the _jupyter-hub-build_ role for this to work.
STS_DICT=$(aws sts assume-role --role-arn arn:aws:iam::553778890976:role/jupyter-hub-build --role-session-name ARandomSessionNameYouPickHere --profile=us-east-1)

export AWS_ACCESS_KEY_ID=$(python -c "print($STS_DICT['Credentials']['AccessKeyId'])")
export AWS_SECRET_ACCESS_KEY=$(python -c "print($STS_DICT['Credentials']['SecretAccessKey'])")
export AWS_SESSION_TOKEN=$(python -c "print($STS_DICT['Credentials']['SessionToken'])")

aws eks update-kubeconfig --name $EKS_CLUSTER_NAME --region=$AWS_REGION

# Check to see if the update was successful
kubectl get svc
```
You can now do full `kubectl` commands against the cluster for a short period of time (about one hour at which the session expires and will need to be renewed.)

__Using Helm__

To interact with the cluster on a more application level (for development and monitoring purposes), we will be using `helm`. The future of `helm` will have the `tiller` part of the app removed. In anticipation, and make the cluster mush safer, we will use a plugin that moves `tiller` outside of the cluster (https://github.com/rimusz/helm-tiller).

```bash
curl https://raw.githubusercontent.com/kubernetes/helm/master/scripts/get | bash
helm init --client-only
helm plugin install https://github.com/rimusz/helm-tiller
helm tiller start  # This starts a shell
```
Get the temporary credentials as described earlier.  

Now you can run `helm` commands.

`helm list` to get info on active releases.

To exit the shell, `helm tiller stop`.

## Troubleshooting

### Out of Storage Space

Sometimes, an user will run out of device space in their notebook. This makes the notebook unresponsive.
Other times, the user might request more storage space because the project they are working on takes more space than allocated by default.  
In these cases, the user's storage will need to be increased.

Four things will need to be done. This will require access to the cluster via `kubectl`. https://kubernetes.io/docs/concepts/storage/persistent-volumes/

1. Make sure that the cluster storage class can support increasing the volume size.

    `kubectl edit storageclass`

    If needed, append to the file the value: `allowVolumeExpansion: true`

1. Find the Persistent Volume Claim (PVC) of the user. The volume claims are in the form `claim-username`.

    `kubectl get pvc -n jupyter`

1. Edit the PVC

    `kubectl edit claim-username -n jupyter`

    Update `spec.resource.requests.storage` to the proper size amount

1. Though the PVC is updated, the volume will not expand automatically. Within the AWS console, find the volume attached to the user and increase the size to match.

1. Restart the notebook server. The user will now have the new expanded volume.

## To delete the cluster

Nothing special needs to take place. Just delete the cloudformation stack and then the pipeline. AWS will take care of the rest of the resources.
