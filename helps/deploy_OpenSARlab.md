
Deploying OpenSARlab to an AWS account
=====================

1. [Prepare CodeCommit Repos](#Prepre CodeCommit repos)
1. [Create an S3 bucket to hold the lambda handler script](#Create an S3 bucket to hold the lambda handler script)
1. [Customize opensarlab_container code for deployment](#Customize opensarlab_container code for deployment)
1. [Customize opensarlab_cluster code for deployment](#Customize opensarlab_cluster code for deployment)
1. [Prepare Lambdas for Cognito](#Prepare Lambdas for Cognito)
1. [Build the Cognito CloudFormation stack](#Build the Cognito CloudFormation stack)
1. [Build the container CloudFormation stack](#Build the container CloudFormation stack)
1. [Build the cluster CloudFormation stack](#Build the cluster CloudFormation stack)
1. [Take care of odds and ends](#Take care of odds and ends)

**A note about deployments:** A deployment of OpenSARlab refers to a standalone instance of OpenSARlab.
If you are setting up OpenSARlab for several classes and/or collaborative groups with disparate needs or funding sources,
it may be useful to give them each their own standalone deployment. This separates user group authentication, 
simplifies billing for each group, and allows for easy cleanup at the end of a project or class (just delete the deployment).
In the following instructions, replace any occurrence of "<deployment_name>" with the deployment name you have chosen.    

Prepare CodeCommit Repos
--------------------
**All the OpenSARlab repos are in the [ASFOpenSARlab](https://github.com/ASFOpenSARlab) Github Org**

1. Clone [opensarlab-container](https://github.com/ASFOpenSARlab/opensarlab-container) to your local computer
1. Clone [opensarlab-cluster](https://github.com/ASFOpenSARlab/opensarlab-cluster) to your local computer
1. Create a <deployment_name>-container CodeCommit repo in your AWS account
1. Create a <deployment_name>-cluster CodeCommit repo
1. Clone the <deployment_name>-container and <deployment_name>-cluster repos to your local computer
1. Copy the contents of the opensarlab-container and opensarlab-cluster repos into the <deployment_name>-container and <deployment_name>-cluster repos, respectively
1. Add, commit, and push your updates to the remote CodeCommit repos

**You should now have container and cluster repos in CodeCommit that are duplicates of those found in ASFOpenSARlab** 

Create an S3 bucket to hold the lambda handler script
--------------------

1. Create an S3 bucket in your AWS account called <deployment_name>-lambda 

Customize opensarlab_container code for deployment
--------------------
**The opensarlab-container repo contains one example profile (named "sar"), which you can reference when creating new profiles**

1. Duplicate the profiles/sar directory and rename it, using your chosen profile name
1. Create and add any additional custom jupyter magic commands to the jupyter-hooks/custom_magics directory
1. Add any additional scripts you may have created for use in your profile to the scripts directory
1. Add any profile test scripts to tests directory
1. Edit sar.sh
    1. Rename sar.sh to <new_profile_name>.sh
    1. Adjust pip installations as needed (note: only add packages here that you need in the base conda environment)
    1. Copy any additional custom Jupyter magic scripts to $HOME/.ipython/profile_default/startup/ (alongside 00-df.py)
    1. Edit the repos being pulled to suit your deployment and profile needs
1. Edit dockerfile
    1. Adjust the packages in the 2nd apt install command to suit your deployment and profile's needs
    1. Add any pip packages you wish installed in the base conda environment
    1. Add any conda packages you wish installed in the base conda environment
    1. Create any conda environments you would like pre-installed before "USER jovyan"
        1. If using environment.yml files, store them in an "envs" directory in <profile_name>/jupyter-hooks, and they will be copied into the container
            1. RUN conda env create -f /etc/jupyter-hooks/envs/<environment_name>_env.yml --prefix /etc/jupyter-hooks/envs/<environment_name>
    1. Run any tests for this profile that you added to the tests directory
1. Remove the profiles/sar directory and sar.sh test script, unless you plan to use the sar profile

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
    1. Add a NodeInstanceType parameter for every profile except "sudo"
    1. Remove the example NodeInstanceTypePROFILE1 resource
    1. Add an AutoScalingGroup resource for every profile except "sudo"
    1. Remove the example AutoScalingGroupPROFILE1 resource
    1. Add a LaunchConfiguration for every profile except "sudo"
        1. The server_type in UserData must match profile's server_type that you will use in helm_config.yaml
    1. Remove the example LaunchConfigurationPROFILE1 resource
1. helm_config.yaml
    1. Add new profiles, using the example PROFILE_1 as a template, changing the following:
        1. Change the name of the profile being search for in group_list
        1. Change the display_name
        1. Change the profile description
        1. Change the extra_labels and node_selector server_types to match the server_type used in the profiles LaunchConfiguration in cloudformation.yaml
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
    1. Create a lambda_handler.py file based on lambda_handler.py.example
    1. Adjust email messages to suit the needs of the deployment
    1. zip the file, creating lambda_handler.py.zip
    1. Upload the zip to the <deployment_name>-lambda S3 bucket
        1. After setting up Cognito for the first time, anytime you make changes to this file you will need to:
            1. Change the name of the zip file
            1. Upload it to the <deployment_name>-lambda S3 bucket
            1. Update the EmailLambdaKeyName parameter in the cognito CloudFormation template to match the new filename
            1. After updating the pipeline, set all Cognito triggers to 'None', save them, set them back to the correct lambdas, and save them again

Prepare Lambdas for Cognito
--------------------



Build the Cognito CloudFormation stack
--------------------


Build the container CloudFormation stack
--------------------


Build the cluster CloudFormation stack
--------------------


Take care of odds and ends
--------------------
1. Tag EKS



