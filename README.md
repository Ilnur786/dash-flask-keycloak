This purpose of this library is to provide seamless integration of Plotly Dash or Flask with keycloak via the python-keycloak package.

#### Prerequisites

Prior to using this library, a Keycloak server must be setup. Please refer to the official documentation,

    https://www.keycloak.org/

After setting up the server, create a realm and a client for the application.

In the clients settings, write redirect URI as "your_app_url/keycloak/callback" .

#### Installation

    pip install dash-flask-keycloak

**You can find examples in dash-flask-keycloak/examples**

(Was developed and tested on Ubuntu 20.04, Python 3.8.10 and Keycloak 21.1.1)
