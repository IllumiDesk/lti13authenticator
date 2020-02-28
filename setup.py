#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="hub-lti-auth",
    version="0.1",
    description="OIDC lti auth",
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
