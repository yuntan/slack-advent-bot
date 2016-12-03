import json
import re
import sys
from cgi import FieldStorage
from datetime import datetime as dt
from http.server import BaseHTTPRequestHandler, HTTPServer
from sched import scheduler
from threading import Thread
from typing import List, Optional

import lxml.html
import requests

from config import (BOT_NAME, CHANNEL_ID, FETCH_INTERVAL, HOST,
                    OUTGOING_WEBHOOK_TOKEN, PORT, SLACK_TEST_TOKEN, STORAGE)

TIME_FORMAT = '%Y/%m/%d %H:%M:%S'
RE_QIITA_URL = re.compile(r'http://qiita.com/advent-calendar/\d{4}/[^>]+')
RE_ADVENTAR_URL = re.compile(r'http://www.adventar.org/calendars/\d+')
POST_MESSAGE_URL = 'https://oucc.slack.com/api/chat.postMessage'


def get_qiita_title(url: str) -> str:
    html = requests.get(url).text
    root = lxml.html.fromstring(html)
    return root.cssselect('#main .adventCalendarJumbotron h1')[0]\
        .text_content()


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
        elem[2].get('class') == 'adventCalendarItem_entry'
        else None
        for elem in elems]
    return entry_urls


def get_adventar_title(url: str) -> str:
    html = requests.get(url).text
    root = lxml.html.fromstring(html)
    return root.cssselect('.mod-calendarHeader h2')[0].text


def get_adventar_entries(url: str) -> List[Optional[str]]:
    html = requests.get(url).text
    root = lxml.html.fromstring(html)
    anchors = root.cssselect(
        '.mod-entryList .mod-entryList-body .mod-entryList-url a')
    entry_urls = [a.get('href') if a.get('href') else None for a in anchors]
    return entry_urls


def scheduled_task(sc: scheduler):
    print('start scheduled task')

    with open(STORAGE, mode='rt', encoding='utf-8') as fp:
        storage = json.load(fp)

    for calendar in storage['calendars']:
        url = calendar['url']
        if RE_QIITA_URL.findall(url):
            new_entries = get_qiita_entries(url)
        else:
            new_entries = get_adventar_entries(url)

        idx = [
            i
            for i, old, new
            in zip(range(25), calendar['entry_urls'], new_entries)
            if old != new]

        print('found %d new entries' % len(idx))

        for i in idx:
            text = '%s %d日目 %s' % (calendar['title'], i + 1, new_entries[i])
            post_slack(text)

        calendar['entry_urls'] = new_entries

    storage['last_updated'] = dt.now().strftime(TIME_FORMAT)

    with open(STORAGE, mode='wt', encoding='utf-8') as fp:
        json.dump(storage, fp)

    print('end scheduled task')

    # register self for periodic execution
    sc.enter(FETCH_INTERVAL, 1, scheduled_task, (sc,))


def post_slack(text: str):
    print('posting message to slack')

    resp = requests.get(POST_MESSAGE_URL, params={
        'token': SLACK_TEST_TOKEN,
        'channel': CHANNEL_ID,
        'text': text,  # url encoded by requests
        'unfurl_links': 'true',
        'username': BOT_NAME,
        'icon_emoji': ':gift:',
    })
    if resp.status_code == requests.codes.ok and resp.json()['ok']:
        print('posting message done')
    else:
        try:
            message = resp.json()['error']
            print('error posting message %d %s' % (resp.status_code, message))
        except ValueError:
            print('error posting message %d' % resp.status_code)


def register_url(url: str):
    if RE_QIITA_URL.findall(url):
        title = get_qiita_title(url)
        entry_urls = get_qiita_entries(url)
    else:
        title = get_adventar_title(url)
        entry_urls = get_adventar_entries(url)

    with open(STORAGE, mode='rt', encoding='utf-8') as fp:
        storage = json.load(fp)

    storage['calendars'].append({
        'url': url,
        'title': title,
        'entry_urls': entry_urls,
    })

    storage['last_updated'] = dt.now().strftime(TIME_FORMAT)

    with open(STORAGE, mode='wt', encoding='utf-8') as fp:
        json.dump(storage, fp)


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
        if user_name == 'slackbot':
            return
        text = form['text'].value

        print('new message by @%s `%s`' % (user_name, text))

        url = ''
        arr = RE_ADVENTAR_URL.findall(text)
        if arr:
            url = arr[0]
        arr = RE_QIITA_URL.findall(text)
        if arr:
            url = arr[0]

        if url:
            print('url found')
            register_url(url)
            # self.wfile.write(json.dumps({'text': 'OK'}))
            # json.dump({'text': 'OK'}, self.wfile)
            self.wfile.write(b'{"text":"OK"}')
        else:
            print('no url found')

        self.send_response(200)
        self.end_headers()


# {
#   'last_updated': ...,
#   'calendars': [
#     {
#       'url': 'http://...',
#       'title': '...',
#       'entry_urls': ['http://...', ...],
#     },
#     ...
#   ],
# }
def initialize_storage():
    try:
        with open(STORAGE, mode='rt', encoding='utf-8') as fp:
            json.load(fp)
    except FileNotFoundError:
        initial_contents = {
            'last_updated': dt.now().strftime(TIME_FORMAT),
            'calendars': [],
        }
        with open(STORAGE, mode='wt', encoding='utf-8') as fp:
            json.dump(initial_contents, fp)
    except json.JSONDecodeError:
        print('ERROR invalid %s' % STORAGE)
        sys.exit(1)


def main():
    initialize_storage()

    print('schedule task')
    sc = scheduler()
    scheduled_task(sc)
    # sc.run(blocking=False) # not working
    t = Thread(target=sc.run)
    t.daemon = True
    t.start()

    print('start server')
    server = HTTPServer((HOST, PORT), SlackMsgHandler)
    server.serve_forever()


if __name__ == '__main__':
    main()
