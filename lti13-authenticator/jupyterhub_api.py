import os
import json

from tornado.httpclient import AsyncHTTPClient


class JupyterHubAPI:
    def __init__(self, token, url='http://chp:8000/hub/api'):
        self.client = AsyncHTTPClient()
        self.root = os.environ.get('JUPYTERHUB_API_URL', url)
        self.default_headers = {
            'Authorization': f'token {token}',
            'Content-Type': 'application/json'
        }

    async def _request(self, endpoint, **kwargs):
        headers = kwargs.pop('headers', {})
        headers.update(self.default_headers)
        url = f'{self.root}/{endpoint}'
        return await self.client.fetch(url, headers=headers, **kwargs)

    async def create_group(self, name):
        return await self._request(f'groups/{name}', body='', method='POST')

    async def get_group(self, name):
        return await self._request(f'groups/{name}')

    async def create_users(self, *users):
        return await self._request('users', body=json.dumps({'usernames': users}), method='POST')

    async def create_user(self, username):
        return await self._request(f'users/{username}', body='', method='POST')

    async def add_group_members(self, group, *members):
        return await self._request(f'groups/{group}/users', body=json.dumps({'users': members}), method='POST')
