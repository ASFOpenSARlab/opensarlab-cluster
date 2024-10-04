import os
import asyncio
import json
import traceback

from tornado import web
from tornado.httpclient import AsyncHTTPClient
from jupyterhub.auth import Authenticator
from jupyterhub.handlers import BaseHandler
from jupyterhub.utils import maybe_future

from opensarlab.auth import encryptedjwt


class My403Exception(Exception):
    pass


class My401Exception(Exception):
    pass


class PortalAuthLoginHandler(BaseHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.lab_name = os.environ.get("JUPYTERHUB_LAB_NAME", "")
        if not self.lab_name:
            self.log.error("PortalAuth Login lab name not found")
            raise My401Exception("No lab name")

        self.portal_domain = os.environ.get("OPENSCIENCELAB_PORTAL_DOMAIN", "")
        if not self.portal_domain:
            raise My401Exception("No portal domain")

    async def post(self):
        raise My401Exception("Not allowed")

    async def get(self):
        """
        If current JupyterHub user not found, get user info from JWT cookie and login user.
        If cookie not found, GET /portal/hub/auth with JWT cookie and try to sign back in.
        If current JupyterHub user found (and signed in), set Lab JupyterHub cookie and redirect back to original url.
        """
        try:
            self.statsd.incr("login.request")
            user = self.current_user

            if not user:
                portal_cookie = self.get_cookie(f"jupyterhub-portal-jwt")

                # If no Portal cookie, then user is fully signed out, so sign in.
                # If no Portal cookie, then redirect to login
                if portal_cookie is None:
                    next = self.get_argument(
                        "next", default=f"/lab/{self.lab_name}/hub/login"
                    )
                    next = web.escape.url_escape(next)

                    self.redirect(
                        f"{self.portal_domain}/portal/hub/auth?next_url={next}"
                    )
                    return

                try:
                    jwt_data = encryptedjwt.decrypt(portal_cookie)
                except Exception as e:
                    self.log.error(f"PortalAuth Login JWT decryption went wrong: {e}")
                    raise My401Exception(
                        "Something went wrong with jwt authentication. Contact the administrator."
                    )

                if jwt_data is None:
                    self.log.error("No JWT data found")
                    raise My401Exception("No jwt data")

                user = await self.login_user(jwt_data)

            if user:
                # set new login cookie
                # because single-user cookie may have been cleared or incorrect
                self.set_login_cookie(user)
                self.redirect(self.get_next_url(user), permanent=False)
                return

            raise My403Exception("No user found to login")

        except My401Exception as e:
            self.log.error(f"PortalAuth Login 401 error: {e}")
            raise web.HTTPError(401)

        except My403Exception as e:
            self.log.error(f"PortalAuth Login 403 error: {e}")
            raise web.HTTPError(403)

        except Exception as e:
            self.log.error(f"PortalAuth Login 500 error: {e}")
            raise web.HTTPError(500)


class PortalAuthLogoutHandler(BaseHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.lab_name = os.environ.get("JUPYTERHUB_LAB_NAME", "")
        if not self.lab_name:
            self.log.error("PortalAuth Login lab name not found")
            raise My401Exception("No lab name")

        self.portal_domain = os.environ.get("OPENSCIENCELAB_PORTAL_DOMAIN", "")
        if not self.portal_domain:
            raise My401Exception("No portal domain")

    # https://github.com/jupyterhub/jupyterhub/blob/d852d9e37c2f2b60ab41de128885503dc441f009/jupyterhub/handlers/login.py#L15
    @property
    def shutdown_on_logout(self):
        return self.settings.get("shutdown_on_logout", False)

    async def _shutdown_servers(self, user):
        """Shutdown servers for logout
        Get all active servers for the provided user, stop them.
        """
        active_servers = [
            name
            for (name, spawner) in user.spawners.items()
            if spawner.active and not spawner.pending
        ]
        if active_servers:
            self.log.info("Shutting down %s's servers", user.name)
            futures = []
            for server_name in active_servers:
                futures.append(maybe_future(self.stop_single_user(user, server_name)))
            await asyncio.gather(*futures)

    async def get(self):
        """
        Clear Lab JupyterHub cookies and JWT cookie.
        """
        try:
            user = self.current_user
            if user:
                if self.shutdown_on_logout:
                    await self._shutdown_servers(user)

                # Remove jwt cookie
                self.clear_cookie("jupyterhub-portal-jwt", path="/")

                self.clear_login_cookie()
                self.statsd.incr("logout")

                self.log.info(f"User logged out: {user.name}")
            self.redirect(f"{self.portal_domain}/portal/hub/logout", permanent=True)
        except Exception as e:
            raise web.HTTPError(500)


class PortalAuthenticator(Authenticator):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.lab_name = os.environ.get("JUPYTERHUB_LAB_NAME", "")
        if not self.lab_name:
            raise My401Exception("No lab name")

        self.portal_domain = os.environ.get("OPENSCIENCELAB_PORTAL_DOMAIN", "")
        if not self.portal_domain:
            raise My401Exception("No portal domain")

    async def _get_user_data_from_auth_api(self, username: str):
        try:
            body = json.dumps({"username": f"{username}"})
            response = await AsyncHTTPClient().fetch(
                f"{self.portal_domain}/portal/hub/auth", body=body, method="POST"
            )

            if not response.code == 200:
                self.log.error(
                    f"Auth response code is not 200. Code: {response.code}, {response['message']}"
                )
                raise My401Exception()

            response = json.loads(response.body)
            if "ERROR" in response["message"]:
                self.log.error(f"{response['message']}")
                raise My401Exception()

        except Exception as e:
            self.log.error(f"Something went wrong with retrieving authentication. {e}")
            raise My401Exception()

        try:
            user_data = encryptedjwt.decrypt(response["data"])
        except Exception as e:
            self.log.error(f"PortalAuth Login JWT decryption went wrong: {e}")
            raise My401Exception(
                "Something went wrong with jwt authentication. Contact the administrator."
            )

        return user_data

    async def authenticate(self, handler, data=None):
        if data:
            username = str(data["name"])

            # Get updated user data from portal
            user_data = await self._get_user_data_from_auth_api(username=username)

            if user_data is None:
                self.log.error("No JWT data found")
                raise My401Exception("No jwt data")

            # Update cookie with latest user info
            if handler:
                try:
                    encrypt_user_data = encryptedjwt.encrypt(user_data)
                    handler._set_cookie(
                        f"jupyterhub-portal-jwt",
                        encrypt_user_data,
                        encrypted=False,
                        path="/",
                        expires_days=10,
                    )
                    self.log.warning(
                        "jupyterhub-portal-jwt cookie updated with latest user data."
                    )
                except Exception as e:
                    self.log.error(e)
                    raise web.HTTPError(403, "Bad cookie value")
            else:
                self.log.error(
                    "Handler not found in PortalAuthenticator.authenticate. Cookie not updated."
                )

            self.log.warning(
                f"Cheap writers killed Data like Khan in Nemesis. User data: {user_data}"
            )
            try:
                user_data_access_for_lab: dict = user_data.get("lab_access", {}).get(
                    self.lab_name, {}
                )
                if not user_data_access_for_lab:
                    return None

                can_user_access_lab: bool = bool(
                    user_data_access_for_lab.get("can_user_access_lab", False)
                )

                user_data_groups: list = user_data.get("groups", [])
                user_data_roles: list = user_data.get("roles", [])
                is_admin: bool = (
                    "admin" in user_data_roles
                    or f"admin-{self.lab_name}" in user_data_groups
                )

                if can_user_access_lab:
                    return {"name": username, "admin": is_admin}

            except Exception as e:
                self.log.error(f"Portal Auth: Traceback: {traceback.format_exc()}")

        return None

    def get_handlers(self, app):
        return [
            (r"/login", PortalAuthLoginHandler),
            (r"/logout", PortalAuthLogoutHandler),
        ]
