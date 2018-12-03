# ASF Jupyterhub

This documentation is composed of the following sections:

- **Future Tasks**: Items of potential future interest to add to the system broken into two sections.
    - **Feature Items**: Potential features or improvements to existing features that would be beneficial to include. Organized according to my priority estimates which may need to be revised.
    - **Security Items**: Potentially security relevant issues that should be addressed before leaving a deployment unsupervised.
- **System Overview**: An overview of the system as it is currently
- **Configuration**: Information on various the configurable variables in the jupyterhub_config file (both default Jupyterhub configurables and BotoSpawner specific ones) and what the requirements of this type of system are.
- **AWS Resource Setup**: A guide on setting up the current configurations of the AWS resources used by the system.
- **System Setup**: A guide on how to set up the current system.
- **Speculative Advice**: My advice based on what I've learned about the Jupyterhub system so far on specific topics that may or may not be of value.
- **Resources**: Resources that I found useful creating the current system, hopefully they will also be helpful to others.

## Future Tasks

### Features

#### Mandatory

- *Determine Node Specifications*
    - How much processing power will nodes need?
    - How much storage will each node need?
    - How much network latency is acceptable?
    - Relatedly, how long of a start time is acceptable?

#### High Priority

- *Add Authentication*
    - The current system uses the default Jupyterhub authentication method. creating a custom authenticator could make authentication more secure and make new accounts easier to create.
        - The University PAM authentication and the Earthdata authentication system are both potential systems to tie into.

#### Medium Priority

- *Improve User Environment Individualization*
    - Create a user account for the Jupyterhub user their node
        - Run the jupyter-singleuser server as that user (potentially denying sudoer privledges to the user?)
    - Specify the area of th filesystem that the notebook has access to
        - See c.Spawner.notebook_dir and c.Spawner.default_url in jupyterhub_config.py
            - This is likely set through the configuration of jupyterhub-singleuser
- *Add Cleanup Service*
    - Currently a server need to be shut down manually either by the user or an admin.
    - It should be possible to make servers shut down after a certain length of inactivity.
        - See the example [cull_idle_service](https://jupyterhub.readthedocs.io/en/stable/getting-started/services-basics.html?highlight=cull-idle)
- *Add Additional Automation of Configuration*
    - There are several configuration variables that may be able to be consolidated or set automatically.
        - Specifically, the c.Jupyterhub.hub_connect_ip
- *Eliminate Key Pair Conflicts*
    - Under certain circumstances different hubs may interfere with each other's automatic AWS key pair generation. This can be worked around and is fairly specific but may want to be addressed.

#### Low Priority

- *Add Logging to the Spawner*
    - There may also be a way to hook the spawner's logging into the rest of the jupyterhub logging system.
- Use an officially singed ssl cert
    - Apparently self signed certs can cause issues with some browsers

### Security

- *Create Appropriate Security Group*
    - The testing security group for the nodes is likely too broad and should be narrowed.
    - The hub still needs it's own security group.
- *Create Appropriate IAM Role*
    - A less permissive IAM role than the test role should be used.
    - The hub currently needs to:
        - Create and terminate EC2s
        - Upload and Download files from s3
        - Create and attach network interfaces (I think?)
        - Create and assign security groups
    - Some of the hub's permissions requirements may be able to be eliminated by prior set up and configuration of the resources at the cost of the manual set up.
    - Using tag based conditionals may be appropriate to limit the hub's permissions as much as possible.

## System Overview

- *Jupyterhub Overview*
    - The Jupyterhub Documentation can be found [here][1]
    - The Short Version is:
        - Jupyterhub provides a method of centrally managing and accessing many Jupyter Notebook servers
        - The access point for the entire system is the proxy which directs requests to either the hub or the appropriate Notebook server.
        - The hub handles:
            - Authentication
                - Done via the configured Authenticator
            - Creation and Termination of Notebook servers
                - Done via the configured Spawner
        - The hub also provides management tools and can run customized services that can interact with the services
- *The ASF Jupyterhub System*
    - The system currently consists of the BotoSpawner Spawner class and a specialized jupyterhub_config file
    - The jupyterhub_config.py serves the normal role of setting the configuration of the system
        - Differences from the default configuration file:
            - A number of new variables have been added to support configuration of AWS resources used by BotoSpawner.
            - Some configuration variables are programatically set.
            - Some hub setup operations take place in the jupyterhub_config file
    - The BotoSpawner implementation of the Jupyterhub Spawner uses Amazon's Boto3 Python api to spawn new Notebook servers in newly created EC2 instancesa and store user's data in s3
        - The BotoSpawner uses the boto3 api to create a new EC2 instance using preconfigured AWS resources
            - Resources:
                - An AMI to create the EC2 from
                - A Security Group to assign to the Notebook servers
                - An s3 bucket to store user's data
            - Some of these resources are required to be set up manually but some may have defaults created by BotoSpawner if none is provided.
        - Once the instance has been created, the spawned creates an ssh connection to the new EC2 and uses that connection to set up instance specific information:
            - Required information for the Notebook server to connect to the hub.
            - The user's previously saved data from s3.

## Configuration

- *Standard Jupyterhub Configuration*: in jupyterhub_config.py
    - Standard configuration options are documented in default jupyterhub_configuration.py which can be created with the jupyterhub --generate-config -f /location/of/file
    - However, some configuration options are particularly important and/or less well documented:
        - `c.Jupyterhub.bind_url`: Determines the URL for reaching the System
        - `c.Jupyterhub.hub_connect_ip`: The ip or dns name of the hub's server. This is used by the Notebook servers to connect to the hub so if it is not set creation of new servers will time out.
        - `c.Jupyterhub.hub_ip`: The address that the hub listens for the Notebook servers on. Setting to `''` or `'0.0.0.0'` will allow listening on all interfaces. Setting to the public ip of the hub should work as well. This being configured incorrectly will also cause a timeout during the creation of new Notebook servers.
        - `c.Jupyterhub.spawner_class`: Fairly self explanatory, sets the Spawner to use. For using Botospawner set to `'BotoSpawner.BotoSpawner'`
        - `c.JupyterHub.ssl_cert/key`: Also Fairly self explanatory, should only be set if an ssl cert and key are being supplied or generated. If these are supplied https will automatically be used. Remember to change the protocol in the address bar.
        - `c.Spawner.cmd`: The command that should be run on a node to start the single-user Notebook. This is how configuration values for the Notebook server are currently being set.
- *BotoSpawner Specific Configuration*: in jupyterhub_config.py
    - Documentation for these variables is provided in the customized version of jupyterhub_config.py in the jupyter-hub-asf repository and here
    - `BotoSpawner.region_name`: Sets the AWS region to use when creating new nodes. For example: `'us-east-1'`
    - `BotoSpawner.ssh_key`: Sets the AWS keypair to associate with the nodes. Setting this to a key pair that you have access to will allow you to ssh directly into nodes. However, if it is set you will need to supply the hub with the key pair as well in the `/etc/ssh` directory. If this is not set the hub will automatically generate a new key pair to associate with the nodes during it's initial setup. If automatic key generation is used you will need to ssh into the hub first to access the key for the nodes.
        - Important Note: Automatic key pair generation will likely cause issues if multiple hubs are running at the same time, on the same AWS account, both using automatic generation as the second hub will delete the key pair being used by the first.
    - `BotoSpawner.user_startup_script`: Shell script that runs immediately before the Notebook server is started. Intended as a more accessible way to configure the node's environment. Currently unused.
    - `BotoSpawner.image_id`: The id of the AWS AMI to use when creating nodes. The AMI must be supplied and meet certain requirements to successfully spawn Notebook servers(see **AWS Resource Setup**).
    - `BotoSpawner.security_group_id`: The id of the AWS security group that should be used by the nodes. The security group must be supplied and meet certain requirements to successfully spawn Notebook servers(see **AWS Resource Setup**).
    - `BotoSpawner.instance_type`: The type of EC2 instance to use when creating nodes, for example: `'t2.nano'`. If unset, the Spawner will default to a `t2.nano`, the smallest available type.
    - `BotoSpawner.user_data_bucket`: The name of the s3 bucket to use when retrieving previously saved data. If unset all data left on the node will be deleted when the Notebook server is shut down.
- *Singleuser Notebook Configuration*
    - In addition to the JupyterHub configuration, the Notebook must also have some configuration values set. These are currently being set via `c.Spawner.cmd` as options during the call to the Notebook.
        - Unfortunately, these settings do not seem to be documented well at all on in the JupyterHub documentation.
    - The current setting that has been working is `'<path/to/jupyterhub-singleuser> --allow-root --ip 0.0.0.0 --port 8080'`

## AWS Resource Setup

- *AMI Setup*
    - Hub Image:
        - Create a baseline instance using the AWS Ubuntu Server 18.04 image and ssh into it
        - Update your apt (`sudo apt update`)
        - Install pip3 (`sudo apt install python3-pip`)
        - Install the latest version of jupyterhub, currently 0.9.4 (`pip3 install jupyterhub==<version>`)
        - Install nmp (`sudo apt install npm`)
        - User npm to install the configurable-http-proxy (`sudo npm install -g configurable-http-proxy`)
        - Make a (shallow) copy of the jupyter-hub-asf repository to get access to BotoSpawner and the customized version of jupyterhub_config.py (`git clone --depth 1 https://github.com/<account_name>/jupyter-hub-asf`)
        - Install boto3 (`pip3 install boto3`)
        - Final Requirements:
            - JupyterHub installation
            - configurable-http-proxy installation
            - BotoSpawner and Customized jupyterhub_config.py
            - boto3 installation
    - Node Image:
        - *Jupyter Requirements*:
            - Create a baseline instance using the AWS Ubuntu Server 18.04 image and ssh into it
            - Update your apt (`sudo apt update`)
            - Install pip3 (`sudo apt install python3-pip`)
            - Install the latest version of JupyterHub, currently 0.9.4 (`pip3 install jupyterhub==<version>`)
            - Install the latest version of Jupyter Notebook, currently 5.7.0 (`pip3 install notebook==<version>`)
            - Final Requirements:
                - JupyterHub
                - Jupyter Notebook
        - *GDAL Requirements*
            - Create a baseline instance using the AWS Ubuntu Server 18.04 image and ssh into it
            - Update your apt (`sudo apt update`)
            - Install pip3 (`sudo apt install python3-pip`)
            - Add the repository to get GDAL from to apt (`sudo apt-add-repository ppa:ubuntugis/ubuntugis-unstable`)
            - Install GDAL (`sudo apt install libgdal-dev`)
            - Check the version of GDAL you have (`gdal-config --version`)
            - Install the python bindings for your GDAL version (`pip3 install pygdal==<latest version compatible with your GDAL>`)
            - Final Requirements:
                - GDAL installation
                - Compatible GDAL python bindings installation
- *Security Group Setup*
    - 

## Resources

- [The AWS Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [This](https://russell.ballestrini.net/filtering-aws-resources-with-boto3/) helpful blog that has at least a few bits of  information about boto3 that isn't clearly explained in the docs.
- [The JupyterHub Documentation][1]

[1]: https://jupyterhub.readthedocs.io/en/stable/index.html#