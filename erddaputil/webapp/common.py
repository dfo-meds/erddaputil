import zirconium as zr
from autoinject import injector
import os
import hashlib
import secrets
import time
import flask
import base64
import functools
import zrlog
from prometheus_client import Summary
from werkzeug.exceptions import HTTPException
import timeit



def time_with_errors(summary: Summary):

    def outer(fn):

        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            start = timeit.default_timer()
            state = 'success'
            try:
                res = fn(*args, **kwargs)
                if isinstance(res, dict) and 'success' in res and not res['success']:
                    state = 'error'
            except Exception as ex:
                state = 'error'
                raise ex
            finally:
                summary.labels(result=state).observe(max(0.0, timeit.default_timer() - start))
        return wrapped

    return outer


def error_shield(fn):

    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            resp = fn(*args, **kwargs)
            if resp is None:
                return {"success": True, "message": ""}, 200
            elif hasattr(resp, 'state'):
                if resp.state == 'success':
                    return {"success": True, "message": resp.message}, 200
                else:
                    return {"success": False, "message": resp.message}, 200
            else:
                return resp
        except HTTPException as ex:
            return {"success": False, "message": str(ex)}, ex.code
        except Exception as ex:
            zrlog.get_logger("erddaputil.webapp").exception(f"Exception during execution of {fn.__name__}")
            return {"success": False, "message": f"{type(ex).__name__}: {str(ex)}"}, 500

    return wrapped


@injector.injectable_global
class AuthChecker:

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self._log = zrlog.get_logger("erddaputil.webapp.auth")
        self.password_file = self.config.as_path(("erddaputil", "webapp", "password_file"), default=None)
        if not self.password_file:
            self._log.warning(f"Password file is not configured, authentication will not work")
        elif not self.password_file.parent.exists():
            self._log.warning(f"Password file directory does not exist, authentication will not work")
            self.password_file = None
        self.passwords = {}
        self._load_time = None
        self.peppers = self.config.as_list(("erddaputil", "webapp", "peppers"), default=[""])
        self._default_algorithm = self.config.as_str(("erddaputil", "webapp", "password_hash"), default="sha256")
        self._salt_length = self.config.as_int(("erddaputil", "webapp", "salt_length"), default=16)
        self._min_iterations = self.config.as_int(("erddaputil", "webapp", "min_iterations"), default=700000)
        self._iterations_jitter = self.config.as_int(("erddaputil", "webapp", "iterations_jitter"), default=100000)
        self._load_passwords()

    def _load_passwords(self):
        if self.password_file and self.password_file.exists():
            self.passwords = {}
            with open(self.password_file, "r") as h:
                for line in h.readlines():
                    line = line.strip("\r\n\t ")
                    if not line:
                        continue
                    if "||" not in line:
                        continue
                    username, hashname, salt, iterations, phash = line.split("||", maxsplit=4)
                    self.passwords[username] = (hashname, salt, int(iterations), phash)
            self._load_time = os.path.getmtime(self.password_file)
            self._log.info(f"{len(self.passwords)} passwords loaded from {self.password_file}")

    def _save_passwords(self):
        if self.password_file:
            self._log.info(f"Saving passwords to file")
            with open(self.password_file, "w") as h:
                for un in self.passwords:
                    hn, salt, iters, phash = self.passwords[un]
                    h.write(f"{un}||{hn}||{salt}||{iters}||{phash}\n")
        else:
            raise ValueError("No password file set")

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
        full_salt = salt + self.peppers[0]
        phash = hashlib.pbkdf2_hmac(hashname, password.encode("utf-8"), full_salt.encode("utf-8"), iterations)
        self.passwords[username] = (hashname, salt, iterations, phash.hex())
        self._save_passwords()

    def _check_credentials(self, username, password):
        if username in self.passwords:
            hashname, salt, iterations, phash = self.passwords[username]
            for pepper in self.peppers:
                full_salt = salt + pepper
                check_phash = hashlib.pbkdf2_hmac(hashname, password.encode("utf-8"), full_salt.encode("utf-8"), iterations)
                if secrets.compare_digest(check_phash.hex(), phash):
                    self._log.notice(f"Access authorized for {username}")
                    return True
            self._log.warning(f"Access denied for {username} [bad password]")
        else:
            self._log.warning(f"Access denied for {username} [no such user]")
        return False

    def basic_auth(self, credentials):
        try:
            decoded = base64.b64decode(credentials).decode("utf-8")
            if ":" not in decoded:
                self._log.warning("Malformed basic auth header, missing : character")
                return False
            un, pwd = decoded.split(":", maxsplit=1)
            return self.check_credentials(un, pwd)
        except Exception as ex:
            self._log.exception(ex)
            return False

    def handle_auth_header(self, auth_header):
        if auth_header is None or auth_header == "":
            self._log.warning(f"No authorization header present")
            return False
        elif " " not in auth_header:
            self._log.warning("Malformed authorization header")
            return False
        else:
            mode, credentials = auth_header.strip().split(" ", maxsplit=1)
            if mode.lower() == "basic":
                return self.basic_auth(credentials)
            else:
                self._log.warning(f"Unrecognized authorization mode {mode}")
                return False


@injector.inject
def require_login(fn, checker: AuthChecker = None):

    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        auth_header = flask.request.headers.get("Authorization")
        if checker.handle_auth_header(auth_header):
            return fn(*args, **kwargs)
        time.sleep(0.1 + (secrets.randbelow(10) / 10))
        return flask.abort(403)

    return wrapped
