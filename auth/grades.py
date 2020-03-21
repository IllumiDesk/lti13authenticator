import os
import json
import logging

from datetime import datetime

from importlib import import_module

from tornado.httpclient import AsyncHTTPClient
from tornado.log import app_log

from .lms import get_lms_access_token


logger = logging.getLogger(__name__)


class GradesSender:
    def __init__(self, course_id, assignment_name, grades, url):
        self.url = url
        self.course_id = course_id
        self.assignment_name = assignment_name
        self.grades = grades
        logger.debug(
            'Instantiated GradesSender with url %s, course_id %s, assignment_name %s, grades %s' % (
               url, course_id, assignment_name, grades))

    def send(self):
        raise NotImplementedError()


async def send(assignment_name, token, grade, user_id, lineitems, lms):
    headers = {
        'Authorization': '{token_type} {access_token}'.format(**token),
        'Content-Type': 'application/vnd.ims.lis.v2.lineitem+json'
    }
    client = AsyncHTTPClient()
    resp = await client.fetch(lineitems, headers=headers)
    items = json.loads(resp.body)
    logger.debug('Sending grades %s' % items)
    lineitem = None
    for item in items:
        if assignment_name.lower() == item['label'].lower():
            lineitem = item['id']
            logger.debug('Obtained lineitem %s' % item)
    if lineitem is None:
        return
    resp = await client.fetch(lineitem, headers=headers)
    line_item = json.loads(resp.body)
    logger.debug('Fetched lineitem %s' % line_item)
    data = {
        'timestamp': datetime.now().isoformat(),
        'userId': user_id,
        'scoreGiven': grade,
        'scoreMaximum': line_item['scoreMaximum'],
        'gradingProgress': 'FullyGraded',
        'activityProgress': 'Completed',
        'comment': '',
    }
    app_log.info(data)
    headers.update({'Content-Type': 'application/vnd.ims.lis.v1.score+json'})
    url = lineitem + '/scores'
    logger.debug('URL for lineitem %s' % url)
    await client.fetch(url, body=json.dumps(data), method='POST', headers=headers)


class CanvasSender(GradesSender):

    async def send(self):
        token = await get_lms_access_token(
            self.url,
            os.environ['LMS_TOKEN_ENDPOINT'],
            os.environ['PRIVATE_KEY'],
            os.environ['LMS_CLIENT_ID'],
        )
        logger.debug('Sending grades with token %s' % token)
        lms_endpoint = os.environ['LMS_ENDPOINT']
        logger.debug('Sending grades with lms_endpoint %s' % lms_endpoint)
        lineitems = f'{lms_endpoint}/api/lti/courses/{self.course_id}/line_items'
        logger.debug('Sending grades with URL %s' % lineitems)
        for grades in self.grades:
            await send(
                self.assignment_name,
                token,
                grades['grade'],
                grades['user_id'],
                lineitems,
                self.url
            )


def get_sender(course_id, assignment_name, data, url):
    path = os.environ.get('GRADES_SENDER', 'auth.grades.CanvasSender')
    module_path, class_name = path.rsplit('.', 1)
    module = import_module(module_path)
    sender_cls = getattr(module, class_name)
    return sender_cls(course_id, assignment_name, data, url)
