import zirconium as zr
from autoinject import injector
import os
import hashlib
import secrets
import time
import flask
import base64
import functools


@injector.injectable_global
class AuthChecker:

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.password_file = self.config.as_path(("erddaputil", "webapp", "password_file"))
        self.passwords = {}
        self._load_time = None
        self.peppers = self.config.as_list(("erddaputil", "webapp", "peppers"), default=[""])
        self._default_algorithm = self.config.as_str(("erddaputil", "webapp", "password_hash"), default="sha256")
        self._salt_length = self.config.as_int(("erddaputil", "webapp", "salt_length"), default=16)
        self._min_iterations = self.config.as_int(("erddaputil", "webapp", "min_iterations"), default=700000)
        self._iterations_jitter = self.config.as_int(("erddaputil", "webapp", "iterations_jitter"), default=100000)

    def _load_passwords(self):
        if self.password_file and self.password_file.exists():
            self.passwords = {}
            with open(self.password_file, "r") as h:
                for line in h.readlines():
                    line = line.strip("\r\n\t ")
                    if not line:
                        continue
                    if not "||" in line:
                        continue
                    username, hashname, salt, iterations, phash = line.split("||", maxsplit=4)
                    self.passwords[username] = (hashname, salt, int(iterations), phash)
            self._load_time = os.path.getmtime(self.password_file)

    def _save_passwords(self):
        if self.password_file:
            with open(self.password_file, "w") as h:
                for un in self.passwords:
                    hn, salt, iters, phash = self.passwords[un]
                    h.write(f"{un}||{hn}||{salt}||{iters}||{phash}\n")

    def _recheck_password_file(self):
        if self.password_file and self.password_file.exists():
            if os.path.getmtime(self.password_file) > self._load_time:
                self._load_passwords()
                return True
        return False

    def check_credentials(self, username, password):
        # First pass
        if self._check_credentials(username, password):
            return True
        # Check if the password file needs reloading maybe
        elif self._recheck_password_file():
            return self._check_credentials(username, password)
        # Otherwise, attempt was just bad
        return False

    def set_credentials(self, username, password):
        iterations = secrets.randbelow(self._iterations_jitter) + self._min_iterations
        hashname = self._default_algorithm
        salt = secrets.token_hex(self._salt_length)
        phash = hashlib.pbkdf2_hmac(hashname, password, salt + self.peppers[0], iterations)
        self.passwords[username] = (hashname, salt, iterations, phash)
        self._save_passwords()

    def _check_credentials(self, username, password):
        if username in self.passwords:
            hashname, salt, iterations, phash = self.passwords[username]
            for pepper in self.peppers:
                check_phash = hashlib.pbkdf2_hmac(hashname, password, salt + pepper, iterations)
                if secrets.compare_digest(check_phash, phash):
                    return True
        time.sleep(0.1 + (secrets.randbelow(10) / 10))
        return False


@injector.inject
def require_login(fn, checker: AuthChecker = None):

    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        auth_header = flask.request.headers.get("Authorization").strip(" ")
        mode, credentials = auth_header.split(" ", maxsplit=1)
        if mode.lower() == "basic" and _basic_auth_check(credentials, checker):
            return fn(*args, **kwargs)
        return flask.abort(403)

    return wrapped


def _basic_auth_check(credentials, checker: AuthChecker):
    try:
        decoded = base64.b64decode(credentials).decode("utf-8")
        if ":" not in decoded:
            return False
        un, pwd = decoded.split(":", maxsplit=1)
        return checker.check_credentials(un, pwd)
    except Exception as ex:
        return False
