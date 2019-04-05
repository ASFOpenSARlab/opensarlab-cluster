"""
Custom Authenticator to use Earthdata (https://urs.earthdata.nasa.gov) OAuth2 with JupyterHub
"""

import json
import base64
import urllib

from tornado.auth import OAuth2Mixin
from tornado import gen

from tornado.httpclient import HTTPRequest, AsyncHTTPClient

from jupyterhub.auth import LocalAuthenticator

from traitlets import Unicode

from oauthenticator.oauth2 import OAuthLoginHandler, OAuthenticator


EARTHDATA_URL = "https://urs.earthdata.nasa.gov"


class GenericEnvMixin(OAuth2Mixin):
    _OAUTH_ACCESS_TOKEN_URL = '{0}/oauth/token'.format(EARTHDATA_URL)
    _OAUTH_AUTHORIZE_URL = '{0}/oauth/authorize'.format(EARTHDATA_URL)


class GenericLoginHandler(OAuthLoginHandler, GenericEnvMixin):
    pass


class EarthdataOAuthenticator(OAuthenticator):

    # To override OAuthenticator
    login_service = Unicode(
        "EarthdataOAuth2",
        config=True
    )

    # To override OAuthenticator
    login_handler = GenericLoginHandler

    # To override OAuthenticator
    @gen.coroutine
    def authenticate(self, handler, data=None):

        code = handler.get_argument("code")
        http_client = AsyncHTTPClient()

        params = dict(
            redirect_uri=self.get_callback_url(handler),
            code=code,
            grant_type='authorization_code'
        )

        b64key = base64.b64encode(
            bytes(
                "{}:{}".format(self.client_id, self.client_secret),
                "utf8"
            )
        )

        headers = {
            "Accept": "application/json",
            "User-Agent": "JupyterHub",
            "Authorization": "Basic {}".format(b64key.decode("utf8"))
        }
        req = HTTPRequest('{0}/oauth/token'.format(EARTHDATA_URL),
                          method="POST",
                          headers=headers,
                          validate_cert=True,
                          body=urllib.parse.urlencode(params)  # Body is required for a POST...
                          )

        resp = yield http_client.fetch(req)

        resp_json = json.loads(resp.body.decode('utf8', 'replace'))


        endpoint = resp_json['endpoint']
        access_token = resp_json['access_token']
        refresh_token = resp_json.get('refresh_token', None)
        token_type = resp_json['token_type']
        scope = resp_json.get('scope', '')

        if (isinstance(scope, str)):
            scope = scope.split(' ')

        # Determine who the logged in user is
        headers = {
            "Accept": "application/json",
            "User-Agent": "JupyterHub",
            "Authorization": "{} {}".format(token_type, access_token)
        }

        req = HTTPRequest("{0}{1}".format(EARTHDATA_URL, endpoint),
                          method='GET',
                          headers=headers,
                          validate_cert=True,
                          )
        resp = yield http_client.fetch(req)
        resp_json = json.loads(resp.body.decode('utf8', 'replace'))

        return {
            'name': resp_json.get("uid"),
            'auth_state': {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'oauth_user': resp_json,
                'scope': scope,
            }
        }


class LocalGenericOAuthenticator(LocalAuthenticator, EarthdataOAuthenticator):

    """A version that mixes in local system user creation"""
    pass
