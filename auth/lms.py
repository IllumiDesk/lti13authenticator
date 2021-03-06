import json
import jwt
import logging
import os
import re
import shutil
import time
import urllib
import uuid

from pathlib import Path

from tornado.log import app_log
from tornado.httpclient import HTTPClientError
from tornado.httpclient import AsyncHTTPClient

from nbgrader.api import Gradebook
from nbgrader.api import InvalidEntry

from .jupyterhub_api import JupyterHubAPI


logger = logging.getLogger(__name__)


def email_to_username(email):
    if not email:
        raise ValueError("Email is empty")
    username = email.split('@')[0]
    username = username.split('+')[0]
    username = re.sub(r'\([^)]*\)', '', username)
    logger.debug('Username from email is %s' % username)
    return re.sub(r'[^\w-]+', '', username)


async def get_lms_access_token(iss, token_endpoint, private_key, client_id, scope=None):
    token_params = {
        'iss': iss,
        'sub': client_id,
        'aud': token_endpoint,
        'exp': int(time.time()) + 600,
        'iat': int(time.time()),
        'jti': uuid.uuid4().hex
    }
    logger.debug('Getting lms access token with parameters %s' % token_params)
    token = jwt.encode(
        token_params,
        private_key,
        algorithm='RS256',
    )
    logger.debug('Obtaining token %s' % token)
    scope = scope or ' '.join([
        'https://purl.imsglobal.org/spec/lti-ags/scope/score',
        'https://purl.imsglobal.org/spec/lti-ags/scope/lineitem',
        'https://purl.imsglobal.org/spec/lti-ags/scope/lineitem.readonly'
    ])
    logger.debug('Scope is %s' % scope)
    params = {
        'grant_type': 'client_credentials',
        'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
        'client_assertion': token.decode(),
        'scope': scope
    }
    logger.debug('OAuth parameters are %s' % params)
    client = AsyncHTTPClient()
    body = urllib.parse.urlencode(params)
    try:
        resp = await client.fetch(token_endpoint, method='POST', body=body, headers=None)
    except HTTPClientError as e:
        app_log.info(e.response.body)
        raise
    logger.debug('Token response body is %s' % json.loads(resp.body))
    return json.loads(resp.body)


async def fetch_students_from_lms(org, decoded, iss, lms_token_endpoint):
    token = await get_lms_access_token(
        iss,
        lms_token_endpoint,
        os.environ['PRIVATE_KEY'],
        decoded['aud'],
        scope='https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly'
    )
    logger.debug('Token used to fetch students from LMS %s' % token)
    headers = {
        'Accept': 'application/vnd.ims.lti-nrps.v2.membershipcontainer+json',
        'Authorization': '{token_type} {access_token}'.format(**token)
    }
    logger.debug('Headers used to fetch students from LMS %s' % headers)
    client = AsyncHTTPClient()
    endpoint = decoded['https://purl.imsglobal.org/spec/lti-nrps/claim/namesroleservice']['context_memberships_url']
    logger.debug('Using endpoint %s' % endpoint)
    resp = await client.fetch(endpoint, headers=headers)
    out = json.loads(resp.body)
    logger.debug('Fetch student response body %s' % out)
    course_id = decoded['https://purl.imsglobal.org/spec/lti/claim/context']['title']
    logger.debug('Course id is %s' % course_id)
    students = [s for s in out['members'] if is_student(s)]
    logger.debug('Student list is %s' % students)
    teachers = [t for t in out['members'] if is_teacher(t)]
    logger.debug('Instructor list is %s' % teachers)
    await add_students_to_gradebook(org, course_id, students)
    await add_students_to_jupyterhub(course_id, students)
    await add_teachers_to_jupyterhub(course_id, teachers)


def is_student(member):
    logger.debug('Is student? %s' % member['roles'])
    return 'http://purl.imsglobal.org/vocab/lis/v2/membership#Learner' in member['roles']


def is_teacher(member):
    logger.debug('Is instructor? %s' % member['roles'])
    return 'http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor' in member['roles']


async def add_students_to_gradebook(org, course_id, students):
    username = f'grader-{course_id.lower()}'
    logger.debug('Adding students to gradebook %s' % username)
    db_url = Path('/home', username, course_id, 'gradebook.db')
    logger.debug('DB url to add students %s' % db_url)
    db_url.parent.mkdir(exist_ok=True, parents=True)
    if not db_url.exists():
        db_url.touch()
        shutil.chown(str(db_url), user=10001, group=100)
    gradebook = Gradebook(f'sqlite:///{db_url}', course_id=course_id)
    for student in students:
        username = email_to_username(student['email'])
        try:
            logger.debug('Adding user %s to gradebook' % username)
            gradebook.add_student(username, email=student['email'], lms_user_id=student['user_id'])
        except InvalidEntry as e:
            app_log.debug("Error during adding student to gradebook: %s", e)


async def add_students_to_jupyterhub(course_id, students):
    jupyterhub_api = JupyterHubAPI(os.environ['JUPYTERHUB_API_TOKEN'])
    students_group = f'nbgrader-{course_id}'
    logger.debug('Students group name %s' % students_group)
    try:
        logger.debug('Creating student group %s' % students_group)
        await jupyterhub_api.create_group(students_group)
    except HTTPClientError as e:
        if e.code != 409:
            app_log.exception("Error during teachers group creation")
    await add_users_to_jupyterhub(course_id, students, students_group)


async def add_teachers_to_jupyterhub(course_id, teachers):
    jupyterhub_api = JupyterHubAPI(os.environ['JUPYTERHUB_API_TOKEN'])
    teachers_group = f'formgrade-{course_id}'
    logger.debug('Instrutors group name %s' % teachers_group)
    try:
        logger.debug('Creating instructor group %s' % teachers_group)
        await jupyterhub_api.create_group(teachers_group)
    except HTTPClientError as e:
        if e.code != 409:
            app_log.exception("Error during teachers group creation")
    await add_users_to_jupyterhub(course_id, teachers, teachers_group)


async def add_users_to_jupyterhub(course_id, users, group):
    jupyterhub_api = JupyterHubAPI(os.environ['JUPYTERHUB_API_TOKEN'])
    usernames = []
    for student in users:
        username = email_to_username(student['email'])
        usernames.append(username)
        try:
            logger.debug('Adding user %s to JupyterHub' % username)
            await jupyterhub_api.create_user(username)
        except HTTPClientError as e:
            if e.code == 409:
                continue
            app_log.exception("Error adding user to jupyterhub")
    resp = await jupyterhub_api.get_group(group)
    group_users = json.loads(resp.body)["users"]
    logger.debug('Fetching group with users %s' % json.loads(resp.body)["users"])
    new_users = [user for user in usernames if user not in group_users]
    try:
        logger.debug('Adding user list to JupyterHub')
        await jupyterhub_api.add_group_members(group, *new_users)
    except HTTPClientError as e:
        if e.code != 409:
            app_log.exception("Error during teachers group creation")
