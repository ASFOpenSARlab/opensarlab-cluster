
import os

import z2jh

try:
    os.environ["OAUTH_DNS_NAME"] = z2jh.get_config("custom.OAUTH_DNS_NAME")
    os.environ["OAUTH_JUPYTER_URL"] = z2jh.get_config("custom.OAUTH_JUPYTER_URL")
    os.environ['OAUTH_POOL_NAME'] = z2jh.get_config("custom.OAUTH_POOL_NAME")
    os.environ['REGION_NAME'] = z2jh.get_config('custom.AZ_NAME')[:-1]

    from generic_with_logout import GenericOAuthenticator
    c.JupyterHub.authenticator_class = GenericOAuthenticator

except Exception as e:
    print(e)