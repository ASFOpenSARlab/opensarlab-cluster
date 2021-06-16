
Deploying OpenSARlab to an AWS account
=====================

1. [Create an AWS Cost Allocation Tag](#Create an AWS Cost Allocation Tag)
1. [Take AWS SES out of sandbox](#Take AWS SES out of sandbox)
1. [Setup an iCal calendar for notifications](#Setup an iCal calendar for notifications)
1. [Store your CA certificate](#Store your CA certificate)
1. [Prepare CodeCommit Repos](#Prepre CodeCommit repos)
1. [Create an S3 bucket to hold the lambda handler script](#Create an S3 bucket to hold the lambda handler script)
1. [Customize opensarlab_container code for deployment](#Customize opensarlab_container code for deployment)
1. [Customize opensarlab_cluster code for deployment](#Customize opensarlab_cluster code for deployment)
1. [Build the Cognito CloudFormation stack](#Build the Cognito CloudFormation stack)
1. [Build the container CloudFormation stack](#Build the container CloudFormation stack)
1. [Build the cluster CloudFormation stack](#Build the cluster CloudFormation stack)
1. [Take care of odds and ends](#Take care of odds and ends)

**A note about deployments:** A deployment of OpenSARlab refers to a standalone instance of OpenSARlab.
If you are setting up OpenSARlab for several classes and/or collaborative groups with disparate needs or funding sources,
it may be useful to give them each their own standalone deployment. This separates user group authentication, 
simplifies billing for each group, and allows for easy cleanup at the end of a project or class (just delete the deployment).
In the following instructions, replace any occurrence of "<deployment_name>" with the deployment name you have chosen.    

Create an AWS Cost Allocation Tag
--------------------
**Note: only management accounts can create cost allocation tags**

1. Create a cost allocation tag or have one created by someone with access
    1. Give it an available name that makes sense for tracking deployment names associated with AWS resources
        1. i.e. "deployment_name"
        
Take AWS SES out of sandbox
--------------------
**The AWS Simple Email Service is used by OpenSARlab to send emails to users and administrators. These include
authentication related notifications and storage lifecycle management messages.**

While SES is in sandbox, you are limited to sending 1 email per second with no more than 200 in a 24 hour period, and they
may only be sent from an SES verified address to other SES verified addresses.

Note: Provide a detailed explanation of your SES use and email policies when applying to exit the sandbox or you will be denied.

**Approval can take 24-48 hours** 

1. Follow these [instructions](https://docs.aws.amazon.com/ses/latest/DeveloperGuide/request-production-access.html) to 
take your SES out of sandbox.

Setup an iCal calendar for notifications
--------------------

TODO: finish this section

Store your CA certificate
--------------------
**OpenSARlab will lack full functionality if not using https (SSL certification)**

1. Follow these [instructions](https://docs.aws.amazon.com/acm/latest/userguide/import-certificate.html) to import your CA certificate into the AWS Certificate Manager

Prepare CodeCommit Repos
--------------------
TODO Do this differently 

**All the OpenSARlab repos are in the [ASFOpenSARlab](https://github.com/ASFOpenSARlab) Github Org**

1. Clone [opensarlab-container](https://github.com/ASFOpenSARlab/opensarlab-container) to your local computer
1. Clone [opensarlab-cluster](https://github.com/ASFOpenSARlab/opensarlab-cluster) to your local computer
1. Create a <deployment_name>-container CodeCommit repo in your AWS account
1. Create a <deployment_name>-cluster CodeCommit repo
1. Clone the <deployment_name>-container and <deployment_name>-cluster repos to your local computer
1. Copy the contents of the opensarlab-container and opensarlab-cluster repos into the <deployment_name>-container and <deployment_name>-cluster repos, respectively. Do not copy the git history. 
1. Add, commit, and push your updates to the remote CodeCommit repos

**You should now have container and cluster repos in CodeCommit that are duplicates of those found in ASFOpenSARlab** 

Create an S3 bucket to hold the lambda handler script
--------------------

1. Create an S3 bucket in your AWS account called <deployment_name>-lambda

Customize opensarlab_container code for deployment
--------------------
**The opensarlab-container repo contains one example profile named "sar", which you can reference when creating new profiles**

1. Duplicate the profiles/sar directory and rename it, using your chosen profile name
1. Create and add any additional custom jupyter magic commands to the jupyter-hooks/custom_magics directory
1. Add any additional scripts you may have created for use in your profile to the scripts directory
1. Add any profile test scripts to tests directory
1. Edit sar.sh
    1. Rename sar.sh to <new_profile_name>.sh
    1. Copy any additional custom Jupyter magic scripts to $HOME/.ipython/profile_default/startup/ (alongside 00-df.py)
    1. Edit the repos being pulled to suit your deployment and profile needs
1. Repeat the previous step, adding scripts for any additional profiles
1. Edit dockerfile
    1. Adjust the packages in the 2nd apt install command to suit your deployment and profile needs
    1. Add any pip packages you wish installed in the base conda environment
    1. Add any conda packages you wish installed in the base conda environment
    1. Create any conda environments you would like pre-installed before "USER jovyan"
        1. If using environment.yml files, store them in an "envs" directory in <profile_name>/jupyter-hooks, and they will be copied into the container
            1. RUN conda env create -f /etc/jupyter-hooks/envs/<environment_name>_env.yml --prefix /etc/jupyter-hooks/envs/<environment_name>
    1. Run any tests for this profile that you added to the tests directory
1. Remove the profiles/sar directory and sar.sh test script, unless you plan to use the sar profile
1. Add, commit, and push changes to the remote CodeCommit repo

Customize opensarlab_cluster code for deployment
--------------------
**The opensarlab-cluster repo contains TODO comments everywhere deployment specific edits should be made**

Note: Most IDEs have functionality to easily locate and organize TODOs. Searching the code for "TODO" will also work.

1. hub/etc/jupyterhub/custom/delete_snapshot.py
    1. Edit admin email addresses (2 locations)
1. hub/usr/local/share/jupyterhub/templates/login.html
    1. Edit the images and messages that appear on the login page
1. hub/usr/local/share/jupyterhub/templates/pending.html
    1. Edit the message to users that their account is pending approval
1. cloudformation.yaml
    1. Add a NodeInstanceType parameter for every EC2 type
    1. Remove the example NodeInstanceTypePROFILE1 resource
    1. Add an AutoScalingGroup resource for every NodeInstanceType
    1. Remove the example AutoScalingGroupPROFILE1 resource
    1. Add a LaunchConfiguration for every NodeInstanceType
        1. The server_type in UserData must match profile's server_type that you will use in helm_config.yaml
    1. Remove the example LaunchConfigurationPROFILE1 resource
1. helm_config.yaml
    1. Add new profiles, using the example PROFILE_1 as a template
        1. Reference the [kubespawner docs](https://jupyterhub-kubespawner.readthedocs.io/en/latest/spawner.html) for more options and details
        1. Change the name of the profile being search for in group_list
        1. Change the display_name
        1. Change the profile description
        1. Change the extra_labels and node_selector server_types to match the server_type used in the profiles LaunchConfiguration in cloudformation.yaml
        1. Adjust the path to the postStart lifecycle hook
        1. Adjust the mem_limit
            1. The maximum amount of memory available to each user
            1. <= memory available for EC2 type
        1. Adjust the mem_guarantee (or cpu_guarantee)
            1. The minimum amount of memory guaranteed to each user
            1. If there is not enough memory on any existing node, the autoscaler will spin up a new node
            1. Use the mem_guarantee to determine how nodes should be shared among users
            1. Even if not sharing nodes, do not guarantee all available memory
                1. The node requires some memory for setup (varies and may take some trial and error to figure out how much to reserve)
        1. Adjust the cpu_guarantee (or mem_guarantee)
            1. The minimum EC2 cpu units guaranteed to each user
            1. If there aren't enough cpu units left on a node for the next user, the autoscaler will spin up a new node
            1. Use the cpu_guarantee to determine how nodes should be shared among users
            1. Even if not sharing nodes, do not guarantee all available cpus
                1. The node requires some memory for setup
        1. Adjust the storage capacity
            1. This should match the storage capacity used for all profiles
            1. You can increase volume sizes at a later date
            1. Reducing volume sizes is not advised due to a high likelihood of data loss
    1. Remove the example PROFILE_1
1. lambda_handler.py
    1. Lambdas are used by Cognito event triggers for logging and emailing notifications to users and administrators
    1. Create a lambda_handler.py file based on lambda_handler.py.example
    1. Adjust email messages to suit the needs of the deployment
    1. zip the file, creating lambda_handler.py.zip
    1. Upload the zip to the <deployment_name>-lambda S3 bucket
        1. After setting up Cognito for the first time, anytime you make changes to this file you will need to:
            1. Change the name of the zip file
            1. Upload it to the <deployment_name>-lambda S3 bucket
            1. Update the EmailLambdaKeyName parameter in the cognito CloudFormation template to match the new filename
            1. After updating the pipeline, set all Cognito triggers to 'None', save them, set them back to the correct lambdas, and save them again
1. Add, commit, and push changes to the remote CodeCommit repo

Build the Cognito CloudFormation stack
--------------------

1. Open CloudFormation in the AWS console
    1. Page 1 : **Create stack**
        1. Click the "Create stack" button and select "With new resources (standard)"
        1. Under "Specify template", check "Upload a template file"
        1. Use the file chooser to select **cf-cognito.py** from your local branch of the <deployment_name>-cluster repo 
        1. Click the "Next" button
    1. Page 2: **Specify stack details**
        1. Stack name:
            1. <deployment_name>-auth
        1. AdminEmailAddress:
            1. SES verified email address of the primary administrator
                1. This is the sender address users will see on confirmation, verification, and volume lifecycle emails
        1. AdminEmailSNSArn:
            1. Arn of the above admin email address
                1. Must be AWS SES verified (easy to do in the Amazon Simple Email Service console)
        1. ClusterDomain
            1. Enter the deployment domain, if known (i.e. https://deployment_name.your_domain.tdl)
                1. The placeholder domain can be left in place temporarily if the actual domain is not yet known
        1. CostTagValue
            1. <deployment_name>
        1. EmailLambdaBucketName
            1. <deployment_name>-lambda
        1. EmailLambdaKeyName
            1. lambda_handler.py.zip
        1. Click the "Next" button
    1. Page 3: **Configure stack options**
        1. Tags:
            1. Key: 
                1. Cost allocation tag
            1. Value:
                1. <deployment_name>
        1. Click the "Next" button
    1. Page 4: **Review <deployment_name>-auth**
        1. Review and confirm correctness
        1. Check the box next to "I acknowledge that AWS CloudFormation might create IAM resources"
        1. Click the "Create Stack Button" 
       

Build the container CloudFormation stack
--------------------
**This will create the hub image, images for each profile, and store them in namespaced ECR repos**

1. Open CloudFormation in the AWS console
    1. Page 1 : **Create stack**
        1. Click the "Create stack" button and select "With new resources (standard)"
        1. Under "Specify template", check "Upload a template file"
        1. Use the file chooser to select **cf-container.py** from your local branch of the <deployment_name>-container repo 
        1. Click the "Next" button
    1. Page 2: **Specify stack details**
        1. Stack name:
            1. <deployment_name>-container
        1. CodeCommitSourceBranch:
            1. The name of the production branch of the <deloyment_name>-container CodeCommit repo
        1. CodeCommitSourceRepo:
            1. <deployment_name>-container
        1. CostTagValue
            1. <deployment_name>
    1. Page 3: **Configure stack options**
        1. Tags:
            1. Key: Cost allocation tag
            1. Value: <deployment_name>
        1. Click the "Next" button
    1. Page 4: **Review <deployment_name>-auth**
        1. Review and confirm correctness
        1. Check the box next to "I acknowledge that AWS CloudFormation might create IAM resources"
        1. Click the "Create Stack Button"
1. Open CodePipeline in the AWS console
    1. Open the <deployment_name>-container-Container-Pipeline pipeline and monitor it as it runs
        1. Click the "details" link under each stage action for a closer inspection



Build the cluster CloudFormation stack
--------------------
**This CloudFormation stack dynamically creates a second CloudFormation stack. You will end up with a <deployment_name> stack and
 a <deployment_name>-cluster stack.**

1. Open CloudFormation in the AWS console
    1. Page 1 : **Create stack**
        1. Click the "Create stack" button and select "With new resources (standard)"
        1. Under "Specify template", check "Upload a template file"
        1. Use the file chooser to select **cf-pipeline.py** from your local branch of the <deployment_name>-cluster repo 
        1. Click the "Next" button
    1. Page 2: **Specify stack details**
        1. Stack name:
            1. <deployment_name>-cluster
        1. AdminUserName:
            1. JupyterHub Admin username
                1. Initial default admin with access to the JupyterHub admin and group pages
        1. CertificateArn:
            1. Arn associated with the CA certificate you stored in AWS Certificate Manager
                1. arn:aws:acm:<region>:<account_#>:certificate/<certificate_id>
        1. CodeCommitRepoName:
            1. Name of the CodeCommit repo holding your <deployment_name>-cluster code
        1. CodeCommitBranchName:
            1. Name of the branch holding this deployment's cluster code
        1. ContainerNamespace:
            1. <deployment_name>-container
        1. CostTagKey:
            1. Cost allocation tag
        1. CostTagValue:
            1. <deployment_name>
        1. ICALUrl:
            1. The iCal formatted URL of the calendar used for notifications
        1. JupyterHubURL:
            1. Your custom URL (should match ClusterDomain parameter in <deployment_name>-auth stack)
                1. If left blank, the default load balancer will be used
                1. Can be updated later           
        1. OAuthPoolName:
            1. <deployment_name>-auth 
    1. Page 3: **Configure stack options**
        1. Tags:
            1. Key: Cost allocation tag
            1. Value: <deployment_name>
        1. Click the "Next" button
    1. Page 4: **Review <deployment_name>-auth**
        1. Review and confirm correctness
        1. Check the box next to "I acknowledge that AWS CloudFormation might create IAM resources"
        1. Click the "Create Stack Button"
1. Open CodePipeline in the AWS console
    1. Open the <deployment_name>-Pipeline pipeline and monitor it as it runs
        1. Click the "details" link under each stage action for a closer inspection

Take care of odds and ends
--------------------
TODO Finish this section

1. Create Cognito admin user
1. Tag EKS
1. (optional) Updating lambda_handler.py.zip and Cognito triggers



