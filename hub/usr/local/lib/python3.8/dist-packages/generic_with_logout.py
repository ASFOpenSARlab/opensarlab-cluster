"""
Custom Authenticator to use generic OAuth2 with JupyterHub
"""


import json
import os
import base64
import urllib

import boto3

from tornado import gen
from tornado.httputil import url_concat
from tornado.web import RequestHandler
from tornado.httpclient import HTTPRequest, AsyncHTTPClient
from jupyterhub.handlers import LogoutHandler, BaseHandler
from jupyterhub.auth import LocalAuthenticator
from traitlets import Unicode, Dict, Bool
from oauthenticator.oauth2 import OAuthLoginHandler, OAuthenticator


class GenericParameters():

    _OAUTH_DNS_NAME = os.environ.get('OAUTH_DNS_NAME', '')
    _OAUTH_JUPYTER_URL = os.environ.get('OAUTH_JUPYTER_URL', '')
    _OAUTH_POOL_NAME = os.environ.get('OAUTH_POOL_NAME', '')
    _REGION_NAME = os.environ.get('REGION_NAME', '')

    def _get_client_and_secret(pool_name, region_name):

        # This only works if the parent pod has rights to Cognito
        session = boto3.Session()
        cognito = session.client('cognito-idp', region_name=region_name)

        user_pools = cognito.list_user_pools(MaxResults=10)
        user_pool_ids = [up['Id'] for up in user_pools['UserPools'] if up['Name'] == pool_name]

        if user_pool_ids:
            user_pool_id = user_pool_ids[0]

            # Assume that the user pool has only one client. This is reasonable since the cluster should only need one client.
            pool_clients = cognito.list_user_pool_clients(UserPoolId=user_pool_id)
            pool_client_id = pool_clients['UserPoolClients'][0]['ClientId']
        
            user_client_info = cognito.describe_user_pool_client(UserPoolId=user_pool_id, ClientId=pool_client_id)
            user_client_info = user_client_info['UserPoolClient']

            client_id = user_client_info['ClientId']
            client_secret = user_client_info['ClientSecret']

            return client_id, client_secret

    try:
        _OAUTH_CLIENT_ID, _OAUTH_CLIENT_SECRET = _get_client_and_secret(_OAUTH_POOL_NAME, _REGION_NAME)
    except:
        print("Unable to get Cognito Client and Secret")
        raise

    _OAUTH_ACCESS_TOKEN_URL = f"{_OAUTH_DNS_NAME}/oauth2/token"
    _OAUTH_AUTHORIZE_URL = f"{_OAUTH_DNS_NAME}/oauth2/authorize"
    _OAUTH_LOGOUT_URL = f"{_OAUTH_DNS_NAME}/logout?client_id={_OAUTH_CLIENT_ID}&logout_uri={_OAUTH_JUPYTER_URL}"
    _OAUTH2_TOKEN_URL = f"{_OAUTH_DNS_NAME}/oauth2/token"
    _OAUTH2_USERDATA_URL = f"{_OAUTH_DNS_NAME}/oauth2/userInfo"
    _OAUTH_CALLBACK_URL = f"{_OAUTH_JUPYTER_URL}/hub/oauth_callback"
    _OAUTH_LOGIN_SERVICE = "AWS Cognito"  

class GenericLoginHandler(OAuthLoginHandler):
    pass

class GenericLogoutHandler(LogoutHandler):
    """
    Handle custom logout URLs and token revocation. If a custom logout url
    is specified, the 'logout' button will log the user out of that identity
    provider in addition to clearing the session with Jupyterhub, otherwise
    only the Jupyterhub session is cleared.
    """
    @gen.coroutine
    def get(self):
        user = self.get_current_user()
        if user:
            self.clear_login_cookie()
        self.redirect(GenericParameters._OAUTH_LOGOUT_URL)

class PendingHandler(BaseHandler):
    @gen.coroutine
    def get(self):
        user = self.get_current_user()
        if user:
            self.clear_login_cookie()
        html = self.render_template('pending.html', sync=True)
        self.finish(html)

class GenericOAuthenticator(OAuthenticator):

    login_service = GenericParameters._OAUTH_LOGIN_SERVICE
    oauth_callback_url = GenericParameters._OAUTH_CALLBACK_URL
    authorize_url = GenericParameters._OAUTH_AUTHORIZE_URL
    client_id = GenericParameters._OAUTH_CLIENT_ID
    client_secret = GenericParameters._OAUTH_CLIENT_SECRET 

    login_handler = GenericLoginHandler
    logout_handler = GenericLogoutHandler
    pending_handler = PendingHandler

    def get_handlers(self, app):
        return super().get_handlers(app) + [(r'/logout', self.logout_handler)] + [(r'/pending', self.pending_handler)]

    userdata_url = Unicode(
        GenericParameters._OAUTH2_USERDATA_URL,
        config=True,
        help="Userdata url to get user data login information"
    )
    token_url = Unicode(
        GenericParameters._OAUTH2_TOKEN_URL,
        config=True,
        help="Access token endpoint URL"
    )
    extra_params = Dict(
        help="Extra parameters for first POST request"
    ).tag(config=True)

    username_key = Unicode(
        os.environ.get('OAUTH2_USERNAME_KEY', 'username'),
        config=True,
        help="Userdata username key from returned json for USERDATA_URL"
    )
    userdata_params = Dict(
        help="Userdata params to get user data login information"
    ).tag(config=True)

    userdata_method = Unicode(
        os.environ.get('OAUTH2_USERDATA_METHOD', 'GET'),
        config=True,
        help="Userdata method to get user data login information"
    )

    tls_verify = Bool(
        os.environ.get('OAUTH2_TLS_VERIFY', 'True').lower() in {'true', '1'},
        config=True,
        help="Disable TLS verification on http request"
    )

    basic_auth = Bool(
        os.environ.get('OAUTH2_BASIC_AUTH', 'True').lower() in {'true', '1'},
        config=True,
        help="Disable basic authentication for access token request"
    )

    @gen.coroutine
    def authenticate(self, handler, data=None):

        code = handler.get_argument("code")
        # TODO: Configure the curl_httpclient for tornado
        http_client = AsyncHTTPClient()

        params = dict(
            redirect_uri=self.get_callback_url(handler),
            code=code,
            grant_type='authorization_code'
        )
        params.update(self.extra_params)

        if self.token_url:
            url = self.token_url
        else:
            raise ValueError("Please set the OAUTH2_TOKEN_URL environment variable")

        headers = {
            "Accept": "application/json",
            "User-Agent": "JupyterHub"
        }

        if self.basic_auth:
            b64key = base64.b64encode(
                bytes(
                    "{}:{}".format(self.client_id, self.client_secret),
                    "utf8"
                )
            )
            headers.update({"Authorization": "Basic {}".format(b64key.decode("utf8"))})

        req = HTTPRequest(url,
                          method="POST",
                          headers=headers,
                          validate_cert=self.tls_verify,
                          body=urllib.parse.urlencode(params)  # Body is required for a POST...
                          )

        resp = yield http_client.fetch(req, raise_error=False)

        resp_json = json.loads(resp.body.decode('utf8', 'replace'))

        if 'error' in resp_json:
            if resp_json['error'] == "invalid_grant":
                print("Oops!! Look like you are not allowed access. Is your user disabled?")
                handler.redirect("/pending")
                return {
                    'name': resp_json.get(self.username_key),
                    'auth_state': None
                }
            else:
                raise Exception(resp_json['error'])

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
        if self.userdata_url:
            url = url_concat(self.userdata_url, self.userdata_params)
        else:
            raise ValueError("Please set the OAUTH2_USERDATA_URL environment variable")

        req = HTTPRequest(url,
                          method=self.userdata_method,
                          headers=headers,
                          validate_cert=self.tls_verify,
                          )
        resp = yield http_client.fetch(req)
        resp_json = json.loads(resp.body.decode('utf8', 'replace'))

        if not resp_json.get(self.username_key):
            self.log.error("OAuth user contains no key %s: %s", self.username_key, resp_json)
            return

        return {
            'name': resp_json.get(self.username_key),
            'auth_state': {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'oauth_user': resp_json,
                'scope': scope,
            }
        }
