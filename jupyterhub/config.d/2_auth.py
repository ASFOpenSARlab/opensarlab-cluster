import os

import boto3

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

    ## Set SSO token to secrets path
    secrets_manager = boto3.client('secretsmanager', region_name=f"{z2jh.get_config('custom.AWS_REGION')}")
    _sso_token = secrets_manager.get_secret_value(SecretId=f"sso-token/{z2jh.get_config('custom.AWS_REGION')}-{z2jh.get_config('custom.CLUSTER_NAME')}")
    sso_token_path = os.environ.get('OPENSARLAB_SSO_TOKEN_PATH', '/run/secrets/sso_token')
    with open(sso_token_path, 'w') as f:
        f.write(_sso_token)

except Exception as e:
    print(e)

finally:
    print("Done with extraConfig::auth.py")
