import os
import json
import logging

from pathlib import Path

from josepy.jws import JWS
from josepy.jws import Header

import jwt

from tornado import web
from tornado.httpclient import AsyncHTTPClient

from traitlets import Unicode
from traitlets import Bool

from oauthenticator.oauth2 import OAuthenticator

from .handler import LTI13LoginHandler
from .handler import LTI13CallbackHandler
from .illumidesk import setup_course
from .lms import email_to_username
from .lms import fetch_students_from_lms
from .lms import get_lms_access_token


logger = logging.getLogger(__name__)


async def retrieve_matching_jwk(token, endpoint, verify):
    client = AsyncHTTPClient()
    resp = await client.fetch(endpoint, validate_cert=verify)
    logging.debug('Retrieving matching jwk %s' % json.loads(resp.body))
    return json.loads(resp.body)


async def lti_jwt_decode(token, jwks, verify=True, audience=None):
    if verify is False:
        logging.debug(
            'JWK verification is off, returning token %s' % jwt.decode(token, verify=False))
        return jwt.decode(token, verify=False)
    jwks = await retrieve_matching_jwk(token, jwks, verify)
    jws = JWS.from_compact(bytes(token, 'utf-8'))
    logging.debug('Retrieving matching jws %s' % jws)
    json_header = jws.signature.protected
    header = Header.json_loads(json_header)
    logging.debug('Header from decoded jwt %s' % header)
    key = None
    for jwk in jwks['keys']:
        if jwk['kid'] != header.kid:
            continue
        key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
        logging.debug('Get keys from jwks dict  %s' % key)
    if key is None:
        logging.debug('Key is None, returning None')
        return None
    logging.debug(
        'Returning decoded jwt with token %s key %s and verify %s' %
        (token, key, verify)
    )
    return jwt.decode(
        token,
        key,
        verify,
        audience=audience
    )


class LTI13Authenticator(OAuthenticator):
    login_service = "LTI13"

    login_handler = LTI13LoginHandler
    callback_handler = LTI13CallbackHandler

    endpoint = Unicode(config=True)
    authorize_url = Unicode(config=True)
    token_url = Unicode(config=True)
    setup_courses = Bool(config=True, default=False)

    async def authenticate(self, handler, data=None):
        url = f'https://{handler.request.host}'
        logger.debug('Request host URL %s' % url)
        jwks = f'{self.endpoint}/api/lti/security/jwks'
        logger.debug('JWKS endpoint is %s' % jwks)
        id_token = handler.get_argument('id_token')
        logger.debug('ID token is %s' % id_token)
        decoded = await lti_jwt_decode(id_token, jwks, audience=self.client_id)
        logger.debug('Decoded JWT is %s' % decoded)
        self.decoded = decoded
        if self.decoded is None:
            raise web.HTTPError(403)
        self.course_id = decoded['https://purl.imsglobal.org/spec/lti/claim/context']['label']
        logger.debug('course_label is %s' % self.course_id)
        username = email_to_username(decoded['email'])
        logger.debug('username is %s' % self.username)
        lms_course_id = decoded['https://purl.imsglobal.org/spec/lti-ags/claim/endpoint']['lineitems'].split('/')[-2]
        logger.debug('lms_course_id is %s' % self.username)
        org = handler.request.host.split('.')[0]
        logger.debug('org is %s' % org)
        if self.setup_courses:
            response = await setup_course(org, self.course_id, handler.request.host, int(lms_course_id))
        await fetch_students_from_lms(org, self.decoded, url, self.token_url)
        user_type = 'Instructor'
        if 'http://purl.imsglobal.org/vocab/lis/v2/membership#Learner' in decoded['https://purl.imsglobal.org/spec/lti/claim/roles']:
            user_type = 'Learner'
        logger.debug('user_type is %s' % user_type)
        return {'name': username, 'auth_state': {
            'course_id': self.course_id,
            'is_new_setup': response['is_new_setup'],
            'user_type': user_type,
            'lms_instance': self.endpoint,
            'token': await get_lms_access_token(
                url,
                self.token_url,
                os.environ['PRIVATE_KEY'],
                decoded['aud'],
            )
        }}

    async def pre_spawn_start(self, user, spawner):
        auth_state = await user.get_auth_state()
        if not auth_state:
            logger.debug('auth_state not enabled')
            return
        spawner.course_id = auth_state['course_id']
        logger.debug('Course id from auth_state is: %s' % auth_state['course_id'])
        spawner.environment['LMS_INSTANCE'] = auth_state['lms_instance']
        logger.debug('LMS instance from auth_state: %s' % auth_state['lms_instance'])
        spawner.environment['USER_ROLE'] = auth_state['user_type']
        logger.debug('User role from auth_state: %s' % auth_state['user_type'])
        spawner.environment['TOKEN'] = json.dumps(auth_state['token'])
        logger.debug('Token from auth_state: %s' % auth_state['token'])
