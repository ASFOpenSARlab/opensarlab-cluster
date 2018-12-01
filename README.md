# ASF Jupyterhub

This documentation is composed of the following sections:

- **Future Tasks**: Items of potential future interest to add to the system broken into two sections.
    - **Feature Items**: Potential features or improvements to existing features that would be beneficial to include. Organized according to my priority estimates which may need to be revised.
    - **Security Items**: Potentially security relevant issues that should be addressed before leaving a deployment unsupervised.
- **System Overview**: An overview of the system as it is currently
- **System Setup**: A guide on how to set up the current system
- **Configuration**: Information on various the configurable variables in the jupyterhub_config file (both default Jupyterhub configurables and BotoSpawner specific ones) and what the requirements of this type of system are. 
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
        - Jupyterhub provides a method of centrally managing adn accessing many Jupyter Notebook servers
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



## Resources

- [The AWS Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [This](https://russell.ballestrini.net/filtering-aws-resources-with-boto3/) helpful blog that has at least a few bits of  information about boto3 that isn't clearly explained in the docs.
- [The JupyterHub Documentation][1]

[1]: https://jupyterhub.readthedocs.io/en/stable/index.html#