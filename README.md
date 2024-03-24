This purpose of this library is to provide seamless integration of Plotly Dash or Flask with Keycloak via the dash-flask-keycloak package.

### Prerequisites

Prior to using this library, a Keycloak server must be setup. Please refer to the official documentation,

    https://www.keycloak.org/

After setting up the server, create a realm and a client for the application.

In the clients settings, write redirect URI as "your_app_url/keycloak/callback" .

### Installation

    pip install dash-flask-keycloak

### Motivation

The original project was abandoned and doesn't work with Keyloack higher than 17.0 version.

Also were added:
*     Session state control
*     Access token validation
*     Session lifetime (It's recommended to set "session_lifetime" in app less or equal to a minimal value among SSO Session Idle, SSO Session Max in Keyloak realm settings)


## **You can find examples in dash-flask-keycloak/examples**

(Was developed and tested on Ubuntu 20.04, Python 3.8.10 and Keycloak 21.1.1)
