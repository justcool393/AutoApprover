import psycopg2 as pg
import praw
import os
import time

# Requests' exceptions live in .exceptions and are called errors.
from requests.exceptions import ConnectionError, HTTPError
# Praw's exceptions live in .errors and are called exceptions.
from praw.errors import APIException, ClientException

from urllib.parse import urlparse

USERNAME = os.environ.get("R_USER")
PASSWORD = os.environ.get("R_PASS")
INVITE_TITLE = "invitation to moderate /r/"

RECOVERABLE_EXC = (ConnectionError,
                   HTTPError,
                   APIException,
                   ClientException)

db_url = urlparse(os.environ.get("DATABASE_URL"))
db = pg.connect(
    database=db_url.path[1:],
    user=db_url.username,
    password=db_url.password,
    host=db_url.hostname,
    port=db_url.port
)
cur = db.cursor()


def is_blocked(s):
    s = s.display_name
    cur.execute("SELECT * FROM subreddits WHERE name=%s AND mode=-1", (s,))
    return True if cur.fetchone() else False

def is_all_approved(s):
    s = s.display_name
    cur.execute("SELECT * FROM subreddits WHERE name=%s AND mode=1", (s,))
    return True if cur.fetchone() else False


class BlockedSubredditRemover:
    def __init__(self, r):
        self.r = r
        self.query = "SELECT name FROM subreddits WHERE mode=-1"

    def run(self):
        for row in cur.execute(self.query):
            s = r.get_subreddit(row[0])
            if not s:
                continue
            if s.user_is_moderator:
                s.remove_moderator(self.r.user)


class InvitationAcceptor:
    def __init__(self, r):
        self.r = r
        self.invites = set()
        self.time = time.time()

    def run(self):
        for message in r.get_inbox():
            if int(message.created_utc) <= self.time:
                continue

            if not message.author and message.subject.startswith(INVITE_TITLE):
                if is_blocked(message.subreddit):
                    continue
                self.invites.add(message.subreddit.display_name.lower())
            self.time = time.time()
        self.accept_invites()

    def accept_invites(self):
        for sub in self.invites:
            try:
                self.r.accept_moderator_invite(sub)
            except praw.errors.InvalidInvite:
                pass
        self.invites = set()


class AllApprover:
    def __init__(self, r):
        self.r = r

    def run(self):
        queue = self.r.get_spam()
        for s in queue:
            if is_all_approved(s.subreddit) and s.banned_by is None:
                s.approve()


class ModApprover:
    def __init__(self, r):
        self.r = r

    def run(self):
        queue = self.r.get_unmoderated()
        for s in queue:
            if s.author and s.author in s.subreddit.get_moderators():
                if s.banned_by is None:
                    s.approve()




if __name__ == "__main__":
    r = praw.Reddit("Auto approves items made by moderators (/u/justcool393)")
    r.login(USERNAME, PASSWORD)
    modules = [ModApprover(r), AllApprover(r)]
    low_frequency_mod = [BlockedSubredditRemover(r), InvitationAcceptor(r)]

    while True:
        cycle = 5
        try:
            for m in modules:
                m.run()
            if cycle > 4:
                for lm in low_frequency_mod:
                    lm.run()
                cycle = 0
        except RECOVERABLE_EXC:
            pass
        time.sleep(10)