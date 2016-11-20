import json
import re
import sched
import time
from cgi import FieldStorage
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List, Optional

import lxml.html
import requests

from config import (BOT_NAME, HOST, OUTGOING_WEBHOOK_TOKEN, PORT,
                    POST_MESSAGE_URL, STORAGE)

RE_QIITA_URL = re.compile(r'http://qiita.com/advent-calendar/\d{4}/[^>]+')
RE_ADVENTAR_URL = re.compile(r'http://www.adventar.org/calendars/\d+')


def get_qiita_entries(url: str) -> List[Optional[str]]:
    html = requests.get(url).text
    root = lxml.html.fromstring(html)

    # elems: [<div.adventCalendarItem>]
    elems = root.cssselect('#main .adventCalendarItem')

    # <div.adventCalendarItem>
    #   <div.adventCalendarItem_date>12 / 1</div>
    #   <div.adventCalendarItem_author>...</div>
    #   <div.adventCalendarItem_entry>
    #     <a href="...">...</a>
    #   </div>
    # </div>
    entry_urls = [
        elem[2][0].get('href')
        if len(elem) >= 3 and
        elem[2].get('class') is 'adventCalendarItem_entry'
        else None
        for elem in elems]
    return entry_urls


def get_adventar_entries(url: str) -> List[Optional[str]]:
    html = requests.get(url).text
    root = lxml.html.fromstring(html)
    anchors = root.cssselect(
        '.mod-entryList .mod-entryList-body .mod-entryList-url a')
    entry_urls = [a.get('href') if a.get('href') else None for a in anchors]
    return entry_urls


def scheduled_task():
    with open(STORAGE, mode='rt', encoding='utf-8') as fp:
        storage = json.load(fp)

    for calendar in storage['calendars']:
        url = calendar.url
        if RE_QIITA_URL.findall(url):
            new_entries = get_qiita_entries(url)
        else:
            new_entries = get_adventar_entries(url)

        idx = [i
               for i, old, new
               in zip(range(25), calendar.entry_urls, new_entries)
               if old is not new]

        for i in idx:
            # TODO include calendar name to post
            post_slack(('12/%2d ' % i + 1) + new_entries[i])


def post_slack(text: str):
    url = POST_MESSAGE_URL % text
    # TODO error handling
    requests.get(url)
    print('post_slack')


def register_url(url: str):
    if RE_QIITA_URL.findall(url):
        entry_urls = get_qiita_entries(url)
    else:
        entry_urls = get_adventar_entries(url)

    with open(STORAGE, mode='r+t', encoding='utf-8') as fp:
        storage = json.load(fp)

        storage.calendars.append({'url': url, 'entry_urls': entry_urls})

        fp.write(json.dumps(storage))

    # if RE_ADVENTAR_URL.match(url):
    #     if not storage['adventar_urls']:
    #         storage['adventar_urls'] = []
    #     storage['adventar_urls'].append(url)
    # else:
    #     if not storage['qiita_urls']:
    #         storage['qiita_urls'] = []
    #     storage['qiita_urls'].append(url)


class SlackMsgHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        # parse form data
        form = FieldStorage(self.rfile, self.headers, environ={
            'REQUEST_METHOD': self.command,
            'CONTENT_TYPE': self.headers['Content-Type'],
        })

        if form['token'].value != OUTGOING_WEBHOOK_TOKEN:
            print('error: invalid token')
            return

        # filter user
        user_name = form['user_name'].value
        if user_name == BOT_NAME:
            return
        text = form['text'].value

        print('new message by @%s `%s`' % (user_name, text))

        url = ''
        match = RE_ADVENTAR_URL.match(text)
        if match:
            url = match.group(0)
        match = RE_QIITA_URL.match(text)
        if match:
            url = match.group(0)

        if url:
            print('url found')
            register_url(url)
            self.wfile.write(json.dumps({'text': 'OK'}))
        else:
            print('no url found')

        self.send_response(200)
        self.end_headers()


# {
#   'last_updated': ...,
#   'calendars': [
#     { 'url': 'http://...', 'entry_urls': ['http://...', ...], },
#     ...
#   ],
# }
def initialize_storage():
    try:
        with open(STORAGE, mode='r+t', encoding='utf-8') as f:
            json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        with open(STORAGE, mode='wt', encoding='utf-8') as f:
            storage = {'last_updated': '', 'calendars': []}
            f.write(json.dumps(storage))


def main():
    initialize_storage()

    print('schedule task')
    scheduler = sched.scheduler(
        lambda: datetime.now().minute,
        lambda n: time.sleep(n * 60))
    # schedule task one time par hour
    scheduler.enter(0, 1, scheduled_task)
    scheduler.run(blocking=False)

    print('start server')
    server = HTTPServer((HOST, PORT), SlackMsgHandler)
    server.serve_forever()

if __name__ == '__main__':
    main()
