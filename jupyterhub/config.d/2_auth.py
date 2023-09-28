import os

# This try/except is needed for debugging if a problem occurs. AWS Codebuild doesn't allow for useful error messaging.
try:

    # If an error occurs with setting the auth but JupyterHub still starts, the dummy login will be the default. 
    # This could lead to unauthorized entry. So disable login until the last needed moment.
    print("Disabling login temporarily...")
    c.JupyterHub.authenticator_class = 'nullauthenticator.NullAuthenticator'

    LAB_SHORTNAME = os.environ['JUPYTERHUB_LAB_NAME']
    c.JupyterHub.default_url = f"/lab/{LAB_SHORTNAME}/hub/home"

    c.JupyterHub.tornado_settings = {
        'cookie_options': {
            'expires_days': 1.
        },
        'headers': {
            'x-jupyterhub-lab': LAB_SHORTNAME
        }
    }

    print("All good so far. Setting login to Portal Auth...")
    from jupyterhub.portal_auth import PortalAuthenticator
    c.JupyterHub.authenticator_class = PortalAuthenticator

except Exception as e:
    print(e)

finally:
    print("Done with extraConfig::auth.py")
