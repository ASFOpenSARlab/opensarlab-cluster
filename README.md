# ASF Jupyter Hub

There are two ways to install Jupyter Hub in AWS:

1. Setup using CodePipeline and CloudFormation
1. Use the docs in the [_archive_](https://github.com/asfadmin/asf-jupyter-hub/tree/archive) branch


## Installation of JupyterHub with CodePipeline

In general, the following will be performed:

1. Create an User Role (_jupyter\-hub\-build_)
1. Setup AWS Cognito for authentication
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
                    "cloudformation:*",
                    "ecr:*",
                    "dlm:*"
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
    - (Optional) Any user role ARN. This will allow users to interact directly with cluster via AWS CLI.

### Setup AWS Cognito

While not strictly required, AWS Cognito is used for user authentication. Another OAuth2 provider could be used instead (provided that the proper parameters are given).

Perhaps in the future, everything can be standarized and put into cloudformation.

*It is recommended that once someone signs up for an account that are not deleted. Otherwise, another's data storage could be hijacked.*

1. Go to User Pools: https://console.aws.amazon.com/cognito/users
1. Create an user pool named after the cluster (opensarlab) that will be authenticated. It's recommended that there be one user pool per maturity.
    - Use the defaults and then go through and customize.
    - Various lambda triggers can be used to send automated emails. How to do this will not be shown here.
    - Within `General settings > App clients` section:
        - App client id
        - App client secret
    - Within the `App integration` section (substitute the opensarlab as needed):
        - *Callback URL(s)*: https://opensarlab.asf.alaska.edu/hub/oauth_callback
        - *Sign out URL(s)*: https://opensarlab.asf.alaska.edu
        - Authorization code grant
        - openid
        - *Amazon Cognito domain*: https://opensarlab.auth.us-east-1.amazoncognito.com

### Create a Build Pipeline

Go to https://console.aws.amazon.com/codesuite/codepipeline/pipelines.

Create a new pipeline

- __Pipeline name__: anything you want. It's easier to name the same as the cluster.
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
        - __Parameter overrides__ as described next...

The parameter overrides for the cloudformation template can be the following:

* __VpcId__ (required). The VPC of the worker instances. Within the AWS main menu, select _VPC_. Get the default VPC ID from within _Your VPCs_ (e.g. vpc-4da21e37).
* __Subnets__ (required). List of subnets where workers can be created. Within the AWS main menu, select _VPC_. Choose any number of _Subnet ID_s from within _Subnets_ (e.g. subnet-39a09073,subnet-4388e824).
* __ActiveSubnets__ (required). The subnets actually used by resources in the cluster. Typically only one (e.g., where Availability Zone is -d).
* __CodeBuildServiceRoleArn__ (required). Role externally created to give Code Build permission to use AWS resources (e.g. _jupyter-hub-build_).
* __AdminUserName__ (required). User name of main admin. This name is also whitelisted. Other users will need to be added via the Jupyter Hub admin console. This name MUST be a valid Earthdata user.
* __OAuthDnsName__ (required). AWS Cognito authentication DNS name (e.g., https://opensarlab.auth.us-east-1.amazoncognito.com).
* __OAuthClientId__ (required). AWS Cognito authentication client id.
* __OAuthClientSecret__ (required). AWS Cognito authentication client secret.
* __HubAWSId__ (required). The access key to allow the hub to work with Boto3. Default: "".
* __HubAWSSecret__ (required). The secret key to allow the hub to work with Boto3. Default: "".
* __JupyterHubURL__. Jupyterhub URL used by AWS Cognito authentication. If not given, the default is the load balancer URL (since '' is passed in).
* __ImageName__. Name of ECR image of Jupyter notebook. Default is '553778890976.dkr.ecr.us-east-1.amazonaws.com/asf-franz-labs'. (While ECR is being used in the current setup, any docker registry is allowed.)
* __ImageTag__. Tag of ECR image of Jupyter notebook.
* __NodeImageId__. AMI id for the node instances of EKS. This ID must match the EKS cluster version: https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-ami.html. Default: ami-0eeeef929db40543c.
* __NodeInstanceType__. EC2 instance type for the node instances. Default: m5.2xlarge.
* __NodeAutoScalingGroupMinSize__. Minimum size of Node Group ASG. Default: 2.
* __NodeAutoScalingGroupMaxSize__. Maximum size of Node Group ASG. Set to at least 1 greater than NodeAutoScalingGroupDesiredCapacity. Default: 8.
* __NodeAutoScalingGroupDesiredCapacity__. Desired capacity of Node Group ASG. Default: 2.
* __NodeVolumeSize__. Node volume size (GB). Default: 500.
* __NodeAccessKeyId__. Description: The access key to allow aws cli usage by notebook users. Specific AWS resource access is handled by the user attached to the key. Default "".
* __NodeSecretKey__. The secret key to allow aws cli usage by notebook users. Specific AWS resource access is handled by the user attached to the key. Default: "".
* __LoadBalancerCidrBlock__. The range of allowed IPv4 addresses for the load balancer. This only firewalls the load balancer URL and not the cluster in general. Default: 0.0.0.0/0.
* __CertificateArn__. The ARN of the SSL certificate attached to the load balancer. Default: arn:aws:acm:us-east-1:553778890976:certificate/10791780-75d2-4ef0-bfbc-2c074e94b92b.
* __NodeProxyPort__. The port of the hub proxy service opened to the load balancer.  _This needs to be unique between the load balancer and the hub proxy._ Default: 30052.


They need to be in JSON format like:

```json
{
    "VpcId": "vpc-4da21e37",
    "Subnets": "subnet-39a09073,subnet-4388e824",
    "ActiveSubnets": "subnet-4388e824",
    "CodeBuildServiceRoleArn": "jupyter-hub-build",
    "AdminUserName": "emlundell_test1",
    "JupyterHubURL": "https://opensarlab.asf.alaska.edu",
    "OAuthClientId": "****",
    "OAuthClientSecret": "****",
    "OAuthDnsName": "https://opensarlab.auth.us-east-1.amazoncognito.com",
    "ImageTag":  "2019-08-10-00-15-33",
    "NodeAutoScalingGroupMinSize": "2",
    "NodeAutoScalingGroupMaxSize": "8",
    "NodeAutoScalingGroupDesiredCapacity": "2",
    "NodeAccessKeyId": "*****",
    "NodeSecretKey": "*****",
    "HubAWSId": "******",
    "HubAWSSecret": "********"
}
```

After entering in the parameter overrides, click and review and then __Create__.  

And then wait.

### Add build step to Pipeline and rerun

In the initial creation of the Code Pipeline, a build step was not given. This is intentional. Only after the CloudFormation template is initially built will the Code Build project exist. Thus the build step will need to be added afterwards and the pipeline reran.

Once the full pipeline (including the Code Build parts) has been successfully built, future pipeline runs will be able to run the pipeline as it is.

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

If all goes well, everything will be green and you will have a working cluster.

>If the connection hangs or there is a 502 Gateway error, most likely the ports and/or security groups are not properly configured.

>Note that when initially logging into the opensarlab as an user, the volume for that user hasn't been created yet.
>There will be a self-correcting error displayed that will go away once the volume is formed and attached.

### To delete the cluster

Nothing special needs to take place. Just delete the cloudformation stack and then the pipeline. AWS will take care of the rest of the resources.

## Some important things to note

1. When a volume is created from a snapshot by the code, it is created only in Availability Zone `us-east-1d`.

    Note `--set custom.CLUSTER_NAME=${Cluster},custom.AZ_NAME=${AWS::Region}d` in the cloudformation build spec has `d` set.

    If the `ActiveSubnet` parameter does not match the proper AZ, then the volumes will not mount into the user's pods and error out.

1. There are effectively running three crons for volume/snapshot handling:

    1. EC2 snapshot lifecycle policy (built via cloudformation) at 10 UTC daily.

        Snapshots are only guaranteed to start sometime within the given hour.
        Estimate about 50 GB/hour (120 Mb/s) to backup the initial volume. Subsequent backups are based on differences so should be significantly faster.
        It's important that snapshots be taken before volumes or snapshots are deleted.  

    1. Cron inside `hub` pod to delete volumes (via myHubCron.py in `helm_config.yaml`) at 12 UTC daily.
    1. Cron inside `hub` pod to delete snapshots (via myHubCron.py in `helm_config.yaml`) at 13 UTC daily.


## Manage cluster locally

While not needed to setup the cluster, _kubectl_ locally can be useful in monitoring the health of the cluster and making manual changes (doing so with a heap of caution).

1. Setup kubectl

    It's assumed that kubectl is setup already. If not, follow https://kubernetes.io/docs/tasks/tools/install-kubectl/.

1. Setup awscli>=1.16.158

    It's assumed that aws-cli is setup already. If not, follow https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html   

Once kubectl and aws-cli are installed properly, we can check what EKS clusters are active via `aws eks list-clusters`.

If the cluster that we want is active we can get the _kubeconfig_ file to interact with the cluster.

To help with this, a wrapper script has been written `kubectl-temp.sh`. To make this script even easier to use, on the command line create an alias:

`alias sk='source /path/to/asf-jupyter-hub/kubectl-temp.sh'`

To enable just `sk opensarlab` (or whatever is the cluster name).

You can now do full `kubectl` commands against the cluster for a short period of time (about one hour at which the session expires and will need to be renewed.)
The `kubectl` namespace defaults to `jupyter`.
It is known that the token expired when you get an `error` during a kubectl run. Just run `sk opensarlab` again to refresh the token.

__Using Helm__

To interact with the cluster on a more application level (for custom building), we will be using `helm`. The future of `helm` will have the `tiller` part of the app removed. In anticipation, and to make the cluster much safer, we will use a plugin that moves `tiller` outside of the cluster (https://github.com/rimusz/helm-tiller).

```bash
curl https://raw.githubusercontent.com/kubernetes/helm/master/scripts/get | bash
helm init --client-only
helm plugin install https://github.com/rimusz/helm-tiller
helm tiller start  # This starts a shell
```
As needed, get the temporary kubectl credentials as described earlier.  

Now you can run `helm` commands.

`helm list` to get info on active releases.

To exit the shell, `helm tiller stop`.

If errors occurs while using `helm`, exit the helm shell and restart.

## Troubleshooting

### Out of Storage Space

Sometimes, an user will run out of device space in their notebook. This makes the notebook unresponsive.
Other times, the user might request more storage space because the project they are working on takes more space than allocated by default.  
In these cases, the user's storage will need to be increased.

Four things will need to be done. This will require access to the cluster via `kubectl`. https://kubernetes.io/docs/concepts/storage/persistent-volumes/

1. Stop the notebook server that the volume is attached to.

1. Make sure that the cluster storage class can support increasing the volume size.

    `kubectl edit sc`

    If needed, append to the file the value: `allowVolumeExpansion: true`

1. Within the AWS console, find the EBS volume attached to the user and increase the size to the desired amount.

1. Find the Persistent Volume Claim (PVC) of the user within the cluster as follows. The volume claims are in the form `claim-username`.

    `kubectl get pvc`

1. Edit the PVC

    `kubectl edit claim-username`

    Update `spec.resource.requests.storage` to the proper size amount

1. Restart the user's notebook server. The user will now have the new expanded volume.

### 500 Error on Notebook Startup

If you sign into jupyterhub and get something like the following error:

```
500 : Internal Server Error

Redirect loop detected. Notebook has jupyterhub version 1.0.0, but the Hub expects 0.9.6. Try installing jupyterhub==0.9.6 in the user environment if you continue to have problems.

You can try restarting your server from the home page.
```

Then there is a discrepency between the version of the notebook image and the hub image. While the notebook image isn't jupyterhub, per se, it is tagged with the version of JupyterHub that it's compatible with.
To install a version that works, take note of the Hub version. In the example error above, 0.9.6. We need to find a version of the notebook that matches 0.9.6.
Unfortunately, it's a search and match operation.

*__The following is rough and may be out-of-date. Use with caution.__*

The Hub version is the latest version found in the Helm release. It may be the latest build, though that is not guaranteed.
For the notebook version, go to https://github.com/jupyter/docker-stacks/blob/master/base-notebook/Dockerfile#L103 (or thereabouts) and notice the JupyterHub version.
If this version doesn't match the hub, click on Blame at the top of the GitHub page. On the version line, click on the windows icon until you find a version that matches the Hub.
Click back to the last result. We want the commit just after the wanted version. Click in the commit message and then note the commit hash on `0 comments on commit 46a80c1`.
Search for that commit hash at https://github.com/jupyter/docker-stacks/commits/master. Confirm by commit message.
Look at earlier commits until there is one that is `verified`. Note that commit hash.
Look at https://hub.docker.com/r/jupyter/minimal-notebook/tags for that commit hash. If you can't find it, look at another verified commit.
Update the Dockerfile with the new FROM commit hash, push, and re-build the pipeline. If successful, the build will build pass step 1.
After building, update the build tag (from ECR) in the cloudformation and rebuild JupyterHub.
Restart individual notebook servers with JupyterHub and see if the error is resolved.

### A 500 Error On Login Page

On the login page, you get a 500 error. Using `kubectl logs *hub_pod*`, you see

`gnutls_handshake() failed: An unexpected TLS packet was received.`

It's unknown why it becomes unstable though it does seem to occur sometimes after the cluster is downsized.

To solve this issue, via kubectl, delete the hub. It will autospawn.

### Autoscaler Error During Build

If during a cluster build you get

`Error: UPGRADE FAILED: PodDisruptionBudget.policy "autoscaler-aws-cluster-autoscaler" is invalid: spec: Forbidden: updates to poddisruptionbudget spec are forbidden.`

The k8's manifest for the autoscaler has become corrupted.

To fix:

```
kubectl delete namespace autoscaler
kubectl create namespace autoscaler
```
Rebuild the cluster again.

### Gitpuller Error

On notebook server startup, the gitpuller gives an error with `fatal: unable to write index_file`. This is most likely due to the lack of space within the volume. Increase storage space as described above.

### Issue With Volume Mounts

On notebook server startup, an error includes "list of unmounted volumes="" and times out. Sometimes the server starts after multiple attempts.

This is most likely caused by overcrowding of the node and volumes not being allowed to mount. This in turn can be caused by the autoscaler not working properly. Perhaps the Availability Zone is full. Or the volume has a different AZ as the existing nodes.
