
try:
    # Since the service is in another k8s namespace, it needs to be of the form "http://service_name.namespace"
    c.JupyterHub.services.append(
        {
            'name': 'notifications',
            'url': 'http://notifications.services'
        }
    )

except Exception as e:
    print("Something went wrong with starting the services...")
    print(e)