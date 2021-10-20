
try:
    c.JupyterHub.services.append(
        {
            'name': 'notifications',
            'url': 'http://notifications.notifications'
        }
    )

except Exception as e:
    print("Something went wrong with starting the services...")
    print(e)