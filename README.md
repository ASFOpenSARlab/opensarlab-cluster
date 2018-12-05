# ASF Jupyterhub

This documentation is composed of the following sections:

- **Future Tasks**: Items of potential future interest to add to the system or improve on, broken into two sections.
    - **Feature Items**: Potential features or improvements to existing features that would be beneficial to include. Organized according to my priority estimates which may need to be revised.
    - **Security Items**: Potentially security relevant issues that should be addressed before leaving a deployment unsupervised.
- **System Overview**: An overview of the system as it is currently
- **Configuration**: Information on various configurable variables in the jupyterhub_config file (both default Jupyterhub configurables and BotoSpawner specific ones) and what the requirements of this type of system are.
- **AWS Resource Setup**: A guide on setting up the current configurations of the AWS resources used by the system.
- **System Setup**: A guide on how to set up the current system.
- **Speculative Advice**: My advice based on what I've learned about the Jupyterhub system so far on specific topics that may or may not be of value.
- **Resources**: Resources that I think may be useful to anyone working on this or a similar system.

## Future Tasks

### Features

#### Mandatory

- *Determine Node Specifications*
    - How much processing power will nodes need?
    - How much storage will each node need?
    - How much network latency is acceptable?
    - Relatedly, how long of a start time is acceptable?
    
- *Update Hub IAM Role*
    - The current IAM Role that the hub is using will need to be updated to at least give it down/upload permissions for whatever bucket is used for storage of user's data, currently it is limited to the test bucket
        - A new Role with more precise permissions should be made anyways though

#### High Priority

- *Add Authentication*
    - The current system uses the default JupyterHub authentication method. Creating a custom authenticator could make authentication more secure and make new accounts simpler to manage.
        - The University PAM authentication and the Earthdata authentication system are both potential systems to tie into.
- *Reduce Node Start Times*
    - Currently new Nodes take several minutes to start up. This is primarily due to waiting until the AWS status checks are complete to initiate an ssh connection.
    - We need to make sure that we will be able to connect with ssh to be able to start the Notebook server on the Node but there may be a way to wait less long.
        - We may be able to wait on the network interface being attached.
        - Alternatively we can write our own waiter.

#### Medium Priority

- *Determine Precise Networking Settings*
    - The networking settings that I have been using will work, however, now that there is a working system to test against may be beneficial to go through them more thoroughly and eliminate any excess ones.
- *Improve User Environment Individualization*
    - Create a user account for the Jupyterhub user on their node.
        - Run the jupyter-singleuser server as that user (potentially denying sudoer privledges to the user?)
    - Specify a subset of the filesystem that the notebook has access to
        - See c.Spawner.notebook_dir and c.Spawner.default_url in jupyterhub_config.py
            - This is likely set through the configuration of jupyterhub-singleuser
- *Add Cleanup Service*
    - Currently a server needs to be shut down manually either by the user or an admin.
    - It should be possible to make servers shut down after a certain length of inactivity.
        - See the example [cull_idle_service](https://jupyterhub.readthedocs.io/en/stable/getting-started/services-basics.html?highlight=cull-idle)
- *Add Additional Automation of Configuration*
    - There are several configuration variables that may be able to be consolidated or set automatically.
        - Specifically, c.Jupyterhub.hub_connect_ip
- *Eliminate Key Pair Conflicts*
    - Under certain circumstances different hubs may interfere with each other's automatic AWS key pair generation. This can be worked around and is fairly specific but may want to be addressed.
- *Modify the list of known hosts*
    - When a new Node is being spawned we could add it to the list of known hosts on the Hub.
    - This would allow us to not automatically add hosts to the list.
    
#### Low Priority

- *Add Logging to the Spawner*
    - There may also be a way to hook the spawner's logging into the rest of the JupyterHub logging system.
- *Use an officially singed ssl cert*
    - Apparently self signed certs can cause issues with some browsers.

### Security

- *Create Appropriate Security Group*
    - I think that I have narrowed down the Node and Hub's security groups to only what is required but it would be good to take another look at it.
- *Create Appropriate IAM Role*
    - A less permissive IAM role than the test role should be used.
    - The hub currently needs to:
        - Create and terminate EC2s
        - Create Network Interfaces and associate EC2 instances with them
        - Upload and Download files from s3
        - Create and attach network interfaces
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
                - Done via the Authenticator as configured 
            - Creation and Termination of Notebook servers
                - Done via the Spawner as configured
        - The hub also provides management tools and can run customized services
- *The ASF Jupyterhub System*
    - The system currently consists of the BotoSpawner Spawner class and a specialized jupyterhub_config file
    - The jupyterhub_config.py serves the normal role of setting the configuration of the system
        - Differences from the default configuration file:
            - A number of new variables have been added to support configuration of AWS resources used by BotoSpawner.
            - Some configuration variables are programatically set.
            - Some hub setup operations take place in the jupyterhub_config file
    - The BotoSpawner implementation of the Jupyterhub Spawner uses Amazon's Boto3 Python api to spawn new Notebook servers in newly created EC2 instances and store user's data in s3
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
    - `BotoSpawner.image_id`: The id of the AWS AMI to use when creating nodes. The AMI must be supplied and meet certain requirements to successfully spawn Notebook servers(see [**AWS Resource Setup**][2]).
    - `BotoSpawner.security_group_id`: The id of the AWS security group that should be used by the nodes. The security group must be supplied and meet certain requirements to successfully spawn Notebook servers(see [**AWS Resource Setup**][2]).
    - `BotoSpawner.instance_type`: The type of EC2 instance to use when creating nodes, for example: `'t2.nano'`. If unset, the Spawner will default to a `t2.nano`, the smallest available type.
    - `BotoSpawner.user_data_bucket`: The name of the s3 bucket to use when retrieving previously saved data. If unset all data left on the node will be deleted when the Notebook server is shut down.
- *Singleuser Notebook Configuration*
    - In addition to the JupyterHub configuration, the Notebook must also have some configuration values set. These are currently being set via `c.Spawner.cmd` as options during the call to the Notebook.
        - Unfortunately, the only documentation I have found for these settings is the `jupyterhub-singleuser --help` output. 
    - The current setting that has been working is `'<path/to/jupyterhub-singleuser> --ip 0.0.0.0 --port 8080'`.

## AWS Resource Setup

### AMI Setup

#### Hub Image:
- Create a baseline instance using the AWS Ubuntu Server 18.04 image and open an ssh connection to it
- Update your apt (`sudo apt update`)
- Install pip3 (`sudo apt install python3-pip`)
- Install the latest version of jupyterhub, currently 0.9.4 (`pip3 install jupyterhub==<version>`)
- Install nmp (`sudo apt install npm`)
- User npm to install the configurable-http-proxy (`sudo npm install -g configurable-http-proxy`)
- Make a (shallow) copy of the jupyter-hub-asf repository to get access to BotoSpawner and the customized version of jupyterhub_config.py (`git clone --depth 1 https://github.com/<account_name>/jupyter-hub-asf`)
- Install boto3 (`pip3 install boto3`)
- Install paramiko (`pip3 install paramiko`)
- Final Requirements:
    - JupyterHub installation
    - configurable-http-proxy installation
    - BotoSpawner and Customized jupyterhub_config.py
    - boto3 installation
    - paramiko installation

#### Node Image:
- *Jupyter Requirements*:
    - Create a baseline instance using the AWS Ubuntu Server 18.04 image and open an ssh connection to it
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

### Security Group Setup

- **This documentation should be updated once the security groups are given a thorough review.**
- *Node Security Group*
    - TCP on port 22 (required for the hub to use ssh to start jupyterhub-singleuser)
    - TCP on port 8080 (I believe this is the port through which JupyterHub and jupyter-singleuser communicate)
- *Hub Security Group*
    - The Hub will need all the same access as the Nodes
    - TCP over 8000 (the port it listens on for user access)
    - TCP over 8081 if the Proxy's REST API is being used (the port the proxy's api listens on)

### IAM Setup
- **This documentation should be updated once the hub's IAM Role is given a thorough review.**
- **All of these settings are based on the current configuration that Has been tested to work. It does not represent minimum requirements**
- *Hub IAM Role*
    - EC2FullAccess
    - Full access to only the currently set up test bucket
    - Full list access
- *Node IAM Role*
    - The Nodes do not currently require any IAM role as they are not required to make any requests of AWS

## System Setup
This is a step by step guide on how to recreate the system as it currently is and has been verified to work.
This is **not** an example of the ideal setup.

- Create your required AWS resources
    - Create the [Hub][Hub_Image] and [Node][Node_Image] AMIs
    - Create the Hub and Node's [Security Group][Security_Group_Setup]
    - Create the Hub's [IAM Role][IAM_Setup]
    - Create a new EC2 using the Hub's AMI, Security Group and IAM Role
- Set up the EC2 to be used as the Hub
    - SSH into the EC2
    - Pull the most recent version of the jupyter-hub-asf repository
    - Make sure that jupyterhub-config.py is set correctly (most of this should already be set correctly)
        - Set `c.JupyterHub.bind_url` to `'http://:8000'`
        - Set `c.JupyterHub.hub_bind_url` to `''`
        - Set `c.JupyterHub.hub_conect_ip` to the public dns of the EC2
        - Set `c.JupyterHub.hub_ip` to `'0.0.0.0'`
        - Set `c.JupyterHub.hub_port` to `8080`
        - Set `BotoSpawner.region_name` to `'us-east-1'`
        - Set `BotoSpawner.user_startup_script` to `''`
        - Set `BotoSpawner.image_id` to your node's AMI id
        - Set `BotoSpawner.security_group_id` to your node's security group id
        - Set `BotoSpawner.instance_type` to `'t2.nano'`
        - Set `BotoSpawner.user_data_bucket` to your user data bucket's name
        - Set `c.JupyterHub.spawner_class` to `'BotoSpawner.BotoSpawner'`
        - Set `c.JupyterHub.ssl_cert/key` to the location of your ssl cert/key or the location they will be generated at
        - Set `c.Spawner.cmd` to `'<full path to jupyterhub-singleuser on your Node AMI> --allow-root --ip 0.0.0.0 --port 8080'`
        - Set `c.Spawner.port` to `443`
        - Set `c.Spawner.start_timeout` to `60 * 10`
        - Set `c.Authenticator.whitelist` to `{'<username of a user on the EC2>'}`
    - Set a password for the user specified in `c.Authenticator.whitelist`
    - Start the server with `sudo env PYTHONPATH=<path to jupyter-hub-asf repo>:$PYTHONPATH <full path to jupyterhub> -f <path to modified jupyterhub_config.py>`
- Log in at `https://<EC2 public dns>:8000` (`http` if not using `c.JupyterHub.ssl_cert/key`) using the username and password from the EC2's user.
- **Reminder**: If trying to ssh into a node and using an automatically generated key pair you will need to ssh into the Hub and then the node using the key pair stored there.

## Speculative Advice

### Other Data Persistence Options
There were three reasonable options that I thought of for how to get user's data to and from the Nodes:
1. The Current Solution
    - Any files that should be saved should go in a specific directory on the Node
    - Before the Node shuts down that directory is zipped up and transferred from the Node to the Hub
    - From there the Hub uploads the zipped directory into an S3 bucket
    - When a new Node is spawned the spawner looks in the S3 bucket for a file corresponding to the user the Node is for
        - If there is one it is downloaded by the Hub, transferred to the Node and unzipped
        - If there is no corresponding file a new, empty, file is created to be used in the future
    - Pros:
        - Keeps AWS permissions centralized to the Hub, nodes need to make *no* requests to AWS
        - Requires less infrastructure than other options, other options would still require sshing into the nodes as well as giving AWS permissions to nodes
        - There are other benefits to letting the Hub ssh into the Nodes (can make individualized changes to Nodes, can run the Notebook server as a non root user, etc.)
    - Cons:
        - The zipped data directories have to be transferred twice
            - Depending on the size this may affect startup times for Nodes
2. Direct up/download by Nodes
    - Similar to the current solution only the zipped directory would be uploaded from the Node directly to the S3 bucket
    - Pros:
        - Faster
        - There are other benefits to letting the Hub ssh into the Nodes (can make individualized changes to Nodes, can run the Notebook server as a non root user, etc.
    - Cons:
        - Still requires sshing into the Node to actually trigger the upload so the ssh infrastructure is still needed
        - Nodes would require access to the S3 bucket, which means their own IAM Role
3. AMI saving
    - Instead of saving one directory in S3 just save the whole thing as an AMI
    - Pros:
        - Probably the simplest to implement, should only require boto3
        - Users don't risk losing their files if they forget to put them in the saved directory
    - Cons:
        - Creates a bunch of excess AMIs

#### Changing to Direct upload/download
I'm not sure how much a large user directory might impact startup times for the Nodes. It seems plausible that it will be longer than we would like, so this is a basic overview of what it should take to change to the direct up/download option.

- A new IAM Role with access to whatever bucket is being used will need to be created
- As before the Hub can check to see if the zip file corresponding to the user is in the bucket
- The current code using boto3 to upload the zipped file should be able to be converted into AWS cli commands
- instead of transferring the zip file to the Hub, execute the AWS cli command to upload it to the bucket from the Node via ssh

#### Long Term Strategy
If we want to use a similar JupyterHub setup to serve a large number of users we will probably not want to use any of the above options for user data storage.
The best solution that I have though of is to allow users to supply their own AMI's somehow and update them. This would allow the user to manage whatever software installation they want and keep their files organized as they see fit.
I know that there is a method for allowing the user give input to the spawner immediately before it creates the Notebook server. This might be able to be used to supply the spawner with a user's AMI id.
This sort of system would also allow the user to pick an instance type and storage capacity as well which would also be very valuable in a much larger scale operation with a much more diverse group of users.

## Resources

- [The AWS Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [This](https://russell.ballestrini.net/filtering-aws-resources-with-boto3/) helpful blog that has at least a few bits of  information about boto3 that isn't clearly explained in the docs.
- [The JupyterHub Documentation][1]
- The comments in this repository. I've tried to record a lot of thoughts about possible implementations or improvements to the system in my comments, particularly ones flagged as TODO, if you can't find information about something here or in the JupyterHub or AWS documentation it may be worth scanning through the TODO items.

[1]: https://jupyterhub.readthedocs.io/en/stable/index.html#
[2]: #AWS-Resource-Setup
[Node_Image]: #Node-Image
[Hub_Image]: #Hub-Image
[Security_Group_Setup]: #Security-Group-Setup
[IAM_Setup]: #IAM-Setup