import json
import logging
import urllib

from tornado.httpclient import AsyncHTTPClient


logger = logging.getLogger(__name__)


async def send_assignment_to_illumidesk(decoded, url):
    if decoded['https://purl.imsglobal.org/spec/lti/claim/message_type'] != 'LtiResourceLinkRequest':
        return
    if 'https://purl.imsglobal.org/spec/lti-ags/claim/endpoint' not in decoded:
        return
    target_link_uri = decoded['https://purl.imsglobal.org/spec/lti/claim/target_link_uri']
    logger.debug('target_link_uri is %s' % target_link_uri)
    *_, path = target_link_uri.split('/', 9)
    if not path:
        return
    endpoint = f'{url}/assignments/create/'
    logger.debug('endpoint is %s' % endpoint)
    context = decoded['https://purl.imsglobal.org/spec/lti/claim/context']
    logger.debug('context is %s' % context)
    resource_link = decoded['https://purl.imsglobal.org/spec/lti/claim/resource_link']
    logger.debug('resource_link is %s' % resource_link)
    logger.debug('Using decoded payload to set up body for sending assignment %s' % decoded)
    data = {
        'email': decoded['email'],
        'user_id': decoded['sub'],
        'name': resource_link['title'],
        'description': resource_link['description'],
        'course': context['title'],
        'path': path,
        'lms_assignment_id': resource_link['id'],
        'lms_config': json.dumps({
            'endpoint': decoded['https://purl.imsglobal.org/spec/lti-ags/claim/endpoint'],
            'client_id': decoded['aud'],
        })
    }
    logger.debug('Data to send assignments %s' % data)
    body = urllib.parse.urlencode(data)
    client = AsyncHTTPClient()
    await client.fetch(endpoint, method='POST', headers=None, body=body)


async def setup_course(org, name, domain, lms_course_id):
    client = AsyncHTTPClient()
    data = {
        'org': org,
        'name': name,
        'domain': domain,
        'lms_course_id': lms_course_id,
    }
    url = 'http://setup-course:8000'
    headers = {
        'Content-Type': 'application/json'
    }
    logger.debug('Setting up course with data %s' % data)
    response = await client.fetch(url, method='POST', headers=headers, body=json.dumps(data))
    logger.debug('Received response from setup-course %s' % json.loads(response.body))
    return json.loads(response.body)

async def restart_jupyterhub(org, name, domain, lms_course_id):
    client = AsyncHTTPClient()
    data = {
        'org': org,
        'name': name,
        'domain': domain,
        'lms_course_id': lms_course_id,
    }
    logger.debug('Restarting jupyterhub with data %s' % data)
    url = 'http://setup-course:8000/restart'
    headers = {
        'Content-Type': 'application/json'
    }
    
    await client.fetch(url, method='POST', headers=headers, body=json.dumps(data))
