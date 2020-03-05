#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="lti13authenticator",
    version="0.1.4",
    description="JupyterHub LTI 1.3 Authenticator",
    install_requires=[
        'PyJWT',
        'josepy',
        'ipython',
        'nbgrader',
        'oauthenticator',
        'pyjwkest',
        'pycryptodome',
    ],
    package_data={
        'auth': ["templates/*"],
    },
    packages=find_packages()
)
