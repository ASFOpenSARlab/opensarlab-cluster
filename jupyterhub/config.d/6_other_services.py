try:
    # Since the service is in another k8s namespace, it needs to be of the form "http://service_name.namespace"
    print("No services here at the moment")

    # c.JupyterHub.services is defined eariler in the JupyterHub config

except Exception as e:
    print("Something went wrong with starting the services...")
    print(e)
