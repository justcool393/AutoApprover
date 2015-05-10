import os
import praw
import time

# Requests' exceptions live in .exceptions and are called errors.
from requests.exceptions import ConnectionError, HTTPError
# Praw's exceptions live in .errors and are called exceptions.
from praw.errors import APIException, ClientException, RateLimitExceeded

USERNAME = os.environ.get("R_USER")
PASSWORD = os.environ.get("R_PASS")
INVITE_TITLE = "invitation to moderate /r/"

RECOVERABLE_EXC = (ConnectionError,
                   HTTPError,
                   APIException,
                   ClientException)


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
    modules = [ModApprover(r), InvitationAcceptor(r)]

    while True:
        try:
            for m in modules:
                m.run()
        except RECOVERABLE_EXC:
            pass
        time.sleep(20)