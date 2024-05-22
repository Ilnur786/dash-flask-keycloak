import pathlib
from setuptools import setup, find_packages

HERE = pathlib.Path(__file__).parent

README = (HERE / "README.md").read_text()

setup(
    name="dash-flask-keycloak",
    version="1.3.1",
    description="Extension providing Keycloak integration via the python-keycloak package to the Dash/Flask app",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/Ilnur786/dash-flask-keycloak",
    author="Ilnur Faizrakhmanov, Emil Haldrup Eriksen",
    author_email="ilnurfrwork@gmail.com",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
    ],
    packages=find_packages(),
    # packages=["flask_keycloak", "flask_keycloak.examples"],
    python_requires='>=3.8',
    # include_package_data=True,
    install_requires=["flask>=3.0.0", "PyJWT[crypto]>=2.0.0", "python-keycloak>=3.0.0"],
    keywords='python, dash, flask, keycloak, pyjwt',
)
