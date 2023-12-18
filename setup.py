import pathlib
from setuptools import setup

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setup(
    name="dash-keycloak",
    version="0.0.1",
    description="Extension providing Keycloak integration via the python-keycloak package to the Dash/Flask app",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/thedirtyfew/dash-keycloak",
    author="Ilnur Faizrakhmanov, Emil Haldrup Eriksen",
    author_email="ilnurfrwork@gmail.com",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
    ],
    packages=["flask_keycloak", "flask_keycloak.examples"],
    include_package_data=True,
    install_requires=["flask", "python-keycloak", "dash", "PyJWT[crypto]"],
    # entry_points={
    #     "console_scripts": [
    #         "realpython=reader.__main__:main",
    #     ]
    # },
)
