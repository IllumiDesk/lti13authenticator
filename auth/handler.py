import os
import time
import json
from uuid import uuid4
from secrets import randbits
from urllib.parse import quote, urlparse
from pathlib import Path
from hashlib import md5

from Crypto.PublicKey import RSA
from jwkest import long_to_base64
from tornado import web
from tornado.auth import OAuth2Mixin
from jupyterhub.handlers import BaseHandler
from oauthenticator.oauth2 import OAuthLoginHandler, OAuthCallbackHandler, _serialize_state, guess_callback_uri

from .grades import get_sender


class LTI13LoginHandler(OAuthLoginHandler, OAuth2Mixin):
    def post(self):
        login_hint = self.get_argument('login_hint')
        lti_message_hint = self.get_argument('lti_message_hint')
        client_id = self.get_argument('client_id')
        nonce = str(str(randbits(64)) + str(int(time.time())))
        state = self.get_state()
        self.set_state_cookie(state)
        redirect_uri = guess_callback_uri(
            "https",
            self.request.host,
            self.hub.server.base_url
        )
        params = {
            'response_type': 'id_token',
            'scope': ['openid'],
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'extra_params': {
                'response_mode': 'form_post',
                'lti_message_hint': lti_message_hint,
                'prompt': 'none',
                'login_hint': login_hint,
                'state': state,
                'nonce': nonce,
            }
        }
        self.authorize_redirect(**params)

    def get_state(self):
        next_url = self.get_argument('target_link_uri')
        if next_url:
            next_url = next_url.replace('\\', quote('\\'))
            urlinfo = urlparse(next_url)
            next_url = urlinfo._replace(
                scheme='',
                netloc='',
                path='/' + urlinfo.path.lstrip('/'),
            ).geturl()
        if self._state is None:
            self._state = _serialize_state({
                'state_id': uuid4().hex,
                'next_url': next_url,
            })
        return self._state


class LTI13CallbackHandler(OAuthCallbackHandler):
    async def post(self):
        self.check_state()
        user = await self.login_user()
        if user is None:
            raise web.HTTPError(403)
        self.redirect(self.get_next_url(user))


class JWKS(BaseHandler):
    async def get(self):
        self.set_header('Content-Type', 'application/json')
        private_key = os.environ['PRIVATE_KEY']
        kid = md5(private_key.encode('utf-8')).hexdigest()
        public_key = RSA.importKey(private_key).publickey()
        keys = {'keys': [{
            'kty': 'RSA',
            'alg': 'RS256',
            'use': 'sig',
            'kid': kid,
            'n': long_to_base64(public_key.n),
            'e': long_to_base64(public_key.e),
        }]}
        self.write(json.dumps(keys))


class FileSelectHandler(BaseHandler):
    async def get(self):
        user = self.current_user
        decoded = self.authenticator.decoded
        path = Path(
            os.environ['RESOURCE_DIR'],
            self.authenticator.course_id
        )
        files = []
        for f in self._iterate_dir(path):
            fpath = str(f.relative_to(path))
            url = f'https://{self.request.host}/jupyterhub/user/{user.name}/notebooks/{fpath}'
            files.append({
                'path': fpath,
                'content_items': json.dumps({
                    "@context": "http://purl.imsglobal.org/ctx/lti/v1/ContentItem",
                    "@graph": [{
                        "@type": "LtiLinkItem",
                        "@id": url,
                        "url": url,
                        "title": f.name,
                        "text": f.name,
                        "mediaType": "application/vnd.ims.lti.v1.ltilink",
                        "placementAdvice": {"presentationDocumentTarget": "frame"}
                    }]
                })
            })
        html = self.render_template(
            'file-select.html',
            files=files,
            action_url=decoded['https://purl.imsglobal.org/spec/lti/claim/launch_presentation']['return_url'],
        )
        self.finish(html)

    def _iterate_dir(self, directory):
        for item in directory.iterdir():
            if item.name.startswith('.') or item.name.startswith('submissions'):
                continue
            if item.is_dir():
                yield from self._iterate_dir(item)
            else:
                yield item


class SendGradesHandler(BaseHandler):
    async def post(self, course_id, assignment):
        url = f'https://{self.request.host}'
        data = json.loads(self.request.body)
        sender = get_sender(course_id, assignment, data, url)
        await sender.send()
        self.finish(json.dumps({'message': 'OK'}))
