import os
import json
import logging

from tornado.httpclient import AsyncHTTPClient


logger = logging.getLogger(__name__)


class JupyterHubAPI:
    def __init__(self, token, url='http://chp:8000/hub/api'):
        self.client = AsyncHTTPClient()
        self.root = os.environ.get('JUPYTERHUB_API_URL', url)
        logger.debug('Intantiating JupyterHubAPI with url %s' % self.root)
        self.default_headers = {
            'Authorization': f'token {token}',
            'Content-Type': 'application/json'
        }
        logger.debug('Using default headers %s' % self.default_headers)

    async def _request(self, endpoint, **kwargs):
        headers = kwargs.pop('headers', {})
        headers.update(self.default_headers)
        logger.debug('Using headers in request %s' % headers)
        url = f'{self.root}/{endpoint}'
        logger.debug('URL for request is %s' % url)
        return await self.client.fetch(url, headers=headers, **kwargs)

    async def create_group(self, group_name):
        logger.debug('Creating group with group name %s' % group_name)
        return await self._request(f'groups/{group_name}', body='', method='POST')

    async def get_group(self, group_name):
        logger.debug('Getting group with group name %s' % group_name)
        return await self._request(f'groups/{group_name}')

    async def create_users(self, *users):
        logger.debug('Creating users %s' % users)
        return await self._request('users', body=json.dumps({'usernames': users}), method='POST')

    async def create_user(self, username):
        logger.debug('Creating user %s' % username)
        return await self._request(f'users/{username}', body='', method='POST')

    async def add_group_members(self, group, *members):
        logger.debug('Adding group members %s' % members)
        return await self._request(f'groups/{group}/users', body=json.dumps({'users': members}), method='POST')
