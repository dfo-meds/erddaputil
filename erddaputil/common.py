import threading
from autoinject import injector
import zirconium as zr
import logging
import pathlib
import os
import zrlog

ROOT = pathlib.Path(__file__).absolute().parent


@zr.configure
def _config(app: zr.ApplicationConfig):
    dirs = [
        ROOT,
        pathlib.Path("~").expanduser().absolute(),
        pathlib.Path(".").absolute()
    ]
    extras = os.environ.get("ERDDAPUTIL_CONFIG_PATH", "")
    if extras:
        dirs.extend(extras.split(";"))
    app.register_files(dirs, [".erddaputil.toml"], [".erddaputil.defaults.toml"])


def init_config():
    zrlog.init_logging()


class BaseThread(threading.Thread):

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, log_name: str, loop_delay: float = 0.25, is_daemon: bool = True):
        super().__init__()
        self._log = logging.getLogger(log_name)
        self._halt = threading.Event()
        self._loop_delay = loop_delay
        self.daemon = is_daemon

    def terminate(self):
        self._halt.set()

    @injector.as_thread_run
    def run(self):
        try:
            self._setup()
            while not self._halt.is_set():
                self._run()
                self._sleep(self._loop_delay)
        finally:
            self._cleanup()

    def _sleep(self, time: float):
        if time > 0:
            self._halt.wait(time)

    def _run(self):
        raise NotImplementedError()

    def _setup(self):
        pass

    def _cleanup(self):
        pass
