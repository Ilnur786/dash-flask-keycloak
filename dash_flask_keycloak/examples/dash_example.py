from datetime import timedelta

from dash import dcc, html, Dash
from dash.dependencies import Input, Output
from flask import Flask, session, g

# local imports
from dash_flask_keycloak import FlaskKeycloak

# Setup server.
server = Flask(__name__)

KEYCLOAK_HOST = 'http://127.0.0.1:5555'
APP_HOST = "http://127.0.0.1"
APP_PORT = 5007
CLIENT_ID = 'keycloak_clients'
REALM_NAME = 'dev'
CLIENT_SECRET_KEY = 'vlRBHhqzuqkWPiJisAj8zlFVJNVijWsj'
KEYCLOAK_PYTHON_CERT = False

conf = dict(server_url=KEYCLOAK_HOST,
            client_id=CLIENT_ID,
            realm_name=REALM_NAME,
            client_secret_key=CLIENT_SECRET_KEY,
            verify=KEYCLOAK_PYTHON_CERT)

FlaskKeycloak.build(
    server,
    config_data=conf,
    redirect_uri=f"http://127.0.0.1:{APP_PORT}",
    session_lifetime=timedelta(seconds=10),
    # login_path="/login"
)

# Setup dash app.
app = Dash(
    __name__,
    server=server,
)

app.layout = html.Div(
    id="main",
    children=[
        html.Div(id="greeting"),
        dcc.Link(
            html.Button('Logout',
                        id='logout_button',
                        n_clicks=0),
            href="/logout",
            refresh=True
        )
    ]
)


@app.callback(
    Output('greeting', 'children'),
    [Input('main', 'children')])
def update_greeting(_):
    user = session["user"]
    data = session["data"]
    return "Hello {} - calling from {} \n{}".format(user, g.external_url, data)


if __name__ == '__main__':
    app.run_server(port=APP_PORT)
