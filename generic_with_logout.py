"""
Custom Authenticator to use generic OAuth2 with JupyterHub
"""


import json
import os
import base64
import urllib

from tornado.auth import OAuth2Mixin
from tornado import gen

from tornado.httputil import url_concat
from tornado.web import RequestHandler
from tornado.httpclient import HTTPRequest, AsyncHTTPClient

from jupyterhub.handlers import LogoutHandler, BaseHandler
from jupyterhub.auth import LocalAuthenticator

from traitlets import Unicode, Dict, Bool

from oauthenticator.oauth2 import OAuthLoginHandler, OAuthenticator


class GenericEnvMixin(OAuth2Mixin):
    _OAUTH_ACCESS_TOKEN_URL = os.environ.get('OAUTH2_TOKEN_URL', '')
    _OAUTH_AUTHORIZE_URL = os.environ.get('OAUTH2_AUTHORIZE_URL', '')
    _OAUTH_LOGOUT_URL = os.environ.get('OAUTH_LOGOUT_URL', '')


class GenericLoginHandler(OAuthLoginHandler, GenericEnvMixin):
    pass

class GenericLogoutHandler(LogoutHandler, GenericEnvMixin):
    """
    Handle custom logout URLs and token revocation. If a custom logout url
    is specified, the 'logout' button will log the user out of that identity
    provider in addition to clearing the session with Jupyterhub, otherwise
    only the Jupyterhub session is cleared.
    """
    async def handle_logout(self):
        print("Within custom logout handler. Cleared possible cookie and now redirecting to auth logout.")
        self.redirect(self._OAUTH_LOGOUT_URL)

class PendingHandler(BaseHandler):
    @gen.coroutine
    def get(self):
        user = self.get_current_user()
        if user:
            self.clear_login_cookie()
        html = self.render_template('pending.html')
        self.finish(html)

class GenericOAuthenticator(OAuthenticator):

    login_service = Unicode(
        "GenericOAuth2",
        config=True
    )

    login_handler = GenericLoginHandler
    logout_handler = GenericLogoutHandler
    pending_handler = PendingHandler

    def get_handlers(self, app):
        print("get_handlers")
        print(super().get_handlers(app))
        return super().get_handlers(app) + [(r'/logout', self.logout_handler)] + [(r'/pending', self.pending_handler)]

    userdata_url = Unicode(
        os.environ.get('OAUTH2_USERDATA_URL', ''),
        config=True,
        help="Userdata url to get user data login information"
    )
    token_url = Unicode(
        os.environ.get('OAUTH2_TOKEN_URL', ''),
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


class LocalGenericOAuthenticator(LocalAuthenticator, GenericOAuthenticator):

    """A version that mixes in local system user creation"""
    pass
