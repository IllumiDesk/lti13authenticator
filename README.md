**THIS REPO IS NO LONGER MAINTAINED. PLEASE REFER TO THE [ILLUMIDESK MONOREPO](https://github.com/illumidesk/illumidesk) FOR LTI 1.3 CODE**

# JupyterHub LTI 1.3 Authentication

## Installation

Installation is like any other python package with `pip`:

    pip install git+ssh://git@github.com/IllumiDesk/lti13authenticator.git

## Usage

Add these configuration options to your `jupyterhub_config.py`:

```python
c.Authenticator.enable_auth_state = True
c.JupyterHub.authenticator_class = 'auth.authenticator.LTI13Authenticator'
c.LTI13Authenticator.client_id = '125900000000000001' # from canvas developer key
c.LTI13Authenticator.endpoint = 'https://illumidesk.instructure.com'
c.LTI13Authenticator.token_url = 'https://illumidesk.instructure.com/login/oauth2/token'
c.LTI13Authenticator.authorize_url = 'https://illumidesk.instructure.com/api/lti/authorize_redirect'
```

JupyterHub environment variables:

```python
NFS_ROOT=/mnt/efs/fs1
PRIVATE_KEY='my_rsa_private_key'
```

> Use the `openssl genrsa -out key.pem 4096` to create an RSA private key.

## Learning Management System (LMS) Configuration

Refer to the [user docs](https://docs.illumidesk.com) for installation instructions with your LMS.
