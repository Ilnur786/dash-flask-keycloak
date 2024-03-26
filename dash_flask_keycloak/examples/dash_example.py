from datetime import timedelta

from dash import dcc, html, Dash
from dash.dependencies import Input, Output
from flask import session, g

# local imports
from dash_flask_keycloak import FlaskKeycloak

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


# Setup dash app.
app = Dash(__name__)


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

# Setup should be after layout initialization
FlaskKeycloak.build(
    app,
    config_data=conf,
    redirect_uri=f"http://127.0.0.1:{APP_PORT}",
    session_lifetime=timedelta(hours=12),
    # login_path="/login"
)


@app.callback(
    Output('greeting', 'children'),
    [Input('main', 'children')])
def update_greeting(_):
    user = session["user"]
    data = session["data"]
    return (html.Div(f'Hello {user} - calling from {g.external_url}'),
            html.Div(f"{data}"))


if __name__ == '__main__':
    app.run_server(port=APP_PORT)
