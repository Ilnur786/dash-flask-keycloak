import json
import os
import re
import ssl
import urllib.parse
from typing import Union, List
from uuid import uuid4

import jwt
from flask import Flask, redirect, session, request, Response, g
from jwt import PyJWKClient
from keycloak.exceptions import KeycloakConnectionError, KeycloakAuthenticationError, KeycloakPostError, \
    KeycloakGetError, KeycloakError
from keycloak.keycloak_openid import KeycloakOpenID
from werkzeug.wrappers import Request


class Objectify(object):
    def __init__(self, **kwargs):
        self.__dict__.update({key.lower(): kwargs[key] for key in kwargs})


def check_match_in_list(patterns, to_check):
    if patterns is None or to_check is None:
        return False
    for pattern in patterns:
        if re.search(pattern, to_check):
            return True
    return False


class AuthHandler:
    def __init__(self, app, config, session_interface, keycloak_openid, ssl_context, state_control):
        self.app = app
        self.config = config
        self.session_interface = session_interface
        self.keycloak_openid = keycloak_openid
        # Create object representation of config.
        self.config_object = Objectify(config=config, **config)
        self.ssl_context = ssl_context
        self.state_control = state_control
        self.well_known_metadata = self.keycloak_openid.well_known()

    def is_token_valid(self, request):
        local_session = self.session_interface.open_session(self.config_object, request)
        token = local_session.get("token", None)
        if token is not None:
            # JWT Decode
            jwks_client = PyJWKClient(self.well_known_metadata["jwks_uri"], ssl_context=self.ssl_context)
            signing_key = jwks_client.get_signing_key_from_jwt(token["id_token"])
            try:
                data = jwt.decode(
                    token["id_token"],
                    key=signing_key.key,
                    algorithms=self.well_known_metadata["id_token_signing_alg_values_supported"],
                    audience=self.keycloak_openid.client_id,
                )
            except jwt.InvalidTokenError:
                return False
            # TODO: Should be tested
            # else:
            #     # TODO: What if this condition doesn't pass?
            #     if data == local_session.get("data", None):
            #         return True
        return True

    def is_state_valid(self, request):
        local_session = self.session_interface.open_session(self.config_object, request)
        session_state = local_session.get("state", None)
        request_state = request.args.get("state")
        if session_state is not None and request_state is not None:
            if session_state != request_state:
                return False
        return True

    def is_logged_in(self, request):
        return "token" in self.session_interface.open_session(self.config_object, request)

    def auth_url(self, state, callback_uri):
        if self.state_control:
            auth_url = self.keycloak_openid.auth_url(redirect_uri=callback_uri, scope="openid", state=state)
        else:
            auth_url = self.keycloak_openid.auth_url(redirect_uri=callback_uri, scope="openid", state="")
        return auth_url

    def login(self, request, response, **kwargs):
        try:
            # Get access token from Keycloak.
            try:
                token = self.keycloak_openid.token(**kwargs)
            except KeycloakPostError as e:
                raise e
            # JWT Decode
            jwks_client = PyJWKClient(self.well_known_metadata["jwks_uri"], ssl_context=self.ssl_context)
            signing_key = jwks_client.get_signing_key_from_jwt(token["id_token"])
            #
            data = jwt.decode(
                token["id_token"],
                key=signing_key.key,
                algorithms=self.well_known_metadata["id_token_signing_alg_values_supported"],
                audience=self.keycloak_openid.client_id,
            )
            # Get extra info.
            user = self.keycloak_openid.userinfo(token['access_token'])
            # introspect = self.keycloak_openid.introspect(token['access_token'])
            # Bind info to the session.
            response = self.set_session(request, response, token=token, data=data, user=user)
        except KeycloakAuthenticationError as e:
            return e

        return response

    def set_session(self, request, response, **kwargs):
        session = self.session_interface.open_session(self.config_object, request)
        for kw in kwargs:
            session[kw] = kwargs[kw]
        self.session_interface.save_session(self.config_object, session, response)
        return response

    def clean_session(self, request, response):
        local_session = self.session_interface.open_session(self.config_object, request)
        local_session.clear()
        self.session_interface.save_session(self.config_object, local_session, response)
        return response

    def logout(self, response=None):
        self.keycloak_openid.logout(session["token"]["refresh_token"])
        session.clear()
        return response


class AuthMiddleWare:
    def __init__(self, app, auth_handler, redirect_uri=None, uri_whitelist=None,
                 prefix_callback_path=None, abort_on_unauthorized=None, before_login=None):
        self.app = app
        self.auth_handler = auth_handler
        self._redirect_uri = redirect_uri
        self.uri_whitelist = uri_whitelist
        # Setup uris.
        self.before_login = before_login
        # Optionally, prefix callback path with current path.
        self.callback_path = prefix_callback_path + "/keycloak/callback"
        self.abort_on_unauthorized = abort_on_unauthorized

    def get_auth_uri(self, state, environ):
        return self.auth_handler.auth_url(state, self.get_callback_uri(environ))

    def get_callback_uri(self, environ):
        parse_result = urllib.parse.urlparse(self.get_redirect_uri(environ))
        callback_path = self.callback_path
        # Bind the uris.
        return parse_result._replace(path=callback_path).geturl()

    def get_redirect_uri(self, environ):
        if self._redirect_uri:
            return self._redirect_uri
        else:
            scheme = environ.get("HTTP_X_FORWARDED_PROTO", environ.get("wsgi.url_scheme", "http"))
            host = environ.get("HTTP_X_FORWARDED_SERVER", environ.get("HTTP_HOST"))
            return f"{scheme}://{host}"

    def __call__(self, environ, start_response):

        response = None
        request = Request(environ)
        state = uuid4().hex
        # If the uri has been whitelisted, just proceed.
        if check_match_in_list(self.uri_whitelist, request.path):
            return self.app(environ, start_response)
        # Check token validity, especially token expiring
        if not self.auth_handler.is_token_valid(request):
            response = redirect(self.get_auth_uri(state, environ))
            response = self.auth_handler.clean_session(request, response)
            return response(environ, start_response)
        # Check session state validity
        if self.auth_handler.state_control and not self.auth_handler.is_state_valid(request):
            response = Response("Invalid state", 400)
            response = self.auth_handler.clean_session(request, response)
            return response(environ, start_response)
        # If we are logged in, just proceed.
        if self.auth_handler.is_logged_in(request):
            return self.app(environ, start_response)
        # Before login hook.
        if self.before_login:
            response = self.before_login(request, redirect(self.get_redirect_uri(environ)), self.auth_handler)
            return response(environ, start_response)
        # On callback, request access token.
        if request.path == self.callback_path:
            kwargs = dict(
                # grant_type=["authorization_code"],
                grant_type="authorization_code",
                code=request.args.get("code", "unknown"),
                redirect_uri=self.get_callback_uri(environ))
            response = self.auth_handler.login(request, redirect(self.get_redirect_uri(environ)), **kwargs)
            if isinstance(response, KeycloakError):
                # if response is error, will redirect to the login page
                response = redirect(self.get_auth_uri(state, environ))
                response = self.auth_handler.clean_session(request, response)
                return response(environ, start_response)
        # If unauthorized, redirect to login page.
        if self.callback_path not in request.path:
            if check_match_in_list(self.abort_on_unauthorized, request.path):
                response = Response("Unauthorized", 401)
            else:
                response = redirect(self.get_auth_uri(state, environ))
                if self.auth_handler.state_control:
                    response = self.auth_handler.set_session(request, response, state=state)
        # Save the session.
        if response:
            return response(environ, start_response)
        # Request is authorized, just proceed.
        return self.app(environ, start_response)


class FlaskKeycloak:
    def __init__(self, app, keycloak_openid, redirect_uri=None, uri_whitelist=None, logout_path=None,
                 heartbeat_path=None,
                 login_path=None, prefix_callback_path=None,
                 abort_on_unauthorized=None, before_login=None, ssl_context=None, state_control=False):
        logout_path = '/logout' if logout_path is None else logout_path
        uri_whitelist = [] if uri_whitelist is None else uri_whitelist
        if heartbeat_path is not None:
            uri_whitelist = uri_whitelist + [heartbeat_path]
        if login_path is not None:
            uri_whitelist = uri_whitelist + [login_path]
        # Bind secret key.
        if keycloak_openid._client_secret_key is not None:
            app.config['SECRET_KEY'] = keycloak_openid._client_secret_key
        # Add middleware.
        auth_handler = AuthHandler(app.wsgi_app, app.config, app.session_interface, keycloak_openid, ssl_context,
                                   state_control)
        auth_middleware = AuthMiddleWare(app.wsgi_app, auth_handler, redirect_uri, uri_whitelist,
                                         prefix_callback_path, abort_on_unauthorized, before_login)

        def _save_external_url():
            g.external_url = auth_middleware.get_redirect_uri(request.environ)

        app.before_request(_save_external_url)
        app.wsgi_app = auth_middleware

        # Add logout mechanism.
        if logout_path:
            @app.route(logout_path, methods=["GET", 'POST'])
            def route_logout():
                return auth_handler.logout(redirect(auth_middleware.get_redirect_uri(request.environ)))
        if login_path:
            @app.route(login_path, methods=["GET", 'POST'])
            def route_login():
                if session.get('user') is not None:
                    return redirect(auth_middleware.get_redirect_uri(request.environ))
                if request.method == 'GET':
                    return ('<form method="post">'
                            '<input type="text" name="username" id="un" title="username" placeholder="username"/>'
                            '<input type="password" name="password" id="pw" title="username" placeholder="password"/>'
                            '<button type="submit">Login</button>'
                            '</form>')
                # To be able to obtain data from html login page
                if request.form or ("username" in request.form or "password" in request.form):
                    credentials = request.form.to_dict()
                # To be able to obtain data from request as json
                elif request.json or ("username" in request.json or "password" in request.json):
                    credentials = request.json
                else:
                    return "No username and/or password was specified in request", 400
                response = auth_handler.login(request, redirect(auth_middleware.get_redirect_uri(request.environ)),
                                              **credentials)
                if isinstance(response, KeycloakError):
                    session.clear()
                    return response.error_message, response.response_code
                return response
        if heartbeat_path:
            @app.route(heartbeat_path, methods=['GET'])
            def route_heartbeat_path():
                return "Chuck Norris can kill two stones with one bird."

    @staticmethod
    def build(app: Flask, redirect_uri: str = None, config_path: Union[str, os.PathLike] = None,
              config_data: Union[str, dict] = None,
              logout_path: str = None, heartbeat_path: str = None,
              authorization_settings_path: str = None, uri_whitelist: List[str] = None, login_path: str = None,
              prefix_callback_path: str = '', abort_on_unauthorized: List[str] = None, debug_user=None,
              debug_roles: str = None, ssl_context: ssl.SSLContext = None, state_control: bool = True):
        """
        Build FlaskKeycloak class instance

        :param app: Flask app instance
        :param redirect_uri: target url of the app
        :param config_path: path to the keycloak.json file
        :param config_data: keycloak parameters for KeycloakOpenID
        :param logout_path: logout path
        :param heartbeat_path: heartbeat_path
        :param authorization_settings_path: keycloak authorization settings
        :param uri_whitelist: uri which
        :param login_path: login path
        :param prefix_callback_path: prefix callback path
        :param abort_on_unauthorized: List of url which will abort anyway and redirect to login page
        :param debug_user: username for debug
        :param debug_roles: user roles for debug
        :param ssl_context: custom ssl context for PyJWK client
        :param state_control: if True, will control state parameter in keycloak redirect uri and in session's cookie
        :return: FlaskKeycloak class instance
        """
        try:
            # The oidc json is either read from a file with 'config_path' or is directly passed as 'config_data'
            if not config_data:
                # Read config, assumed to be in Keycloak OIDC JSON format.
                config_path = "keycloak.json" if config_path is None else config_path
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
            else:
                if isinstance(config_data, str):
                    config_data = json.load(config_data)
            keycloak_openid = KeycloakOpenID(**config_data)
            if authorization_settings_path is not None:
                keycloak_openid.load_authorization_config(authorization_settings_path)
        except FileNotFoundError as ex:
            before_login = _setup_debug_session(debug_user, debug_roles)
            # If there is not debug user and no keycloak, raise the exception.
            if before_login is None:
                raise ex
            # Create dummy object, we are bypassing keycloak anyway.
            keycloak_openid = KeycloakOpenID("url", "name", "client_id", "client_secret_key")
        return FlaskKeycloak(app, keycloak_openid, redirect_uri, logout_path=logout_path,
                             heartbeat_path=heartbeat_path, uri_whitelist=uri_whitelist, login_path=login_path,
                             prefix_callback_path=prefix_callback_path,
                             abort_on_unauthorized=abort_on_unauthorized,
                             before_login=_setup_debug_session(debug_user, debug_roles), ssl_context=ssl_context,
                             state_control=state_control)

    @staticmethod
    def try_build(app, **kwargs):
        success = True
        try:
            FlaskKeycloak.build(app, **kwargs)
        except FileNotFoundError:
            app.logger.exception("No keycloak configuration found, proceeding without authentication.")
            success = False
        except IsADirectoryError:
            app.logger.exception("Keycloak configuration was directory, proceeding without authentication.")
            success = False
        except KeycloakConnectionError:
            app.logger.exception("Unable to connect to keycloak, proceeding without authentication.")
            success = False
        except KeycloakGetError:
            app.logger.exception("Encountered keycloak get error, proceeding without authentication.")
            success = False
        return success


def _setup_debug_session(debug_user, debug_roles, debug_token="DEBUG_TOKEN"):
    def _before_login(request, response, auth_handler):
        return auth_handler.set_session(request, response,
                                        token=debug_token,
                                        userinfo=dict(preferred_username=debug_user),
                                        introspect=dict(realm_access=dict(roles=debug_roles)))

    return _before_login if debug_user is not None else None


__all__ = ["FlaskKeycloak"]
