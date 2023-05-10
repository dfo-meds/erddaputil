"""Shared utilities."""
import threading
from autoinject import injector
import zirconium as zr
import logging
import pathlib
import os
import zrlog
import importlib
import timeit
import typing as t

ROOT = pathlib.Path(__file__).absolute().parent


@zr.configure
def _config(app: zr.ApplicationConfig):
    """Setup the configuration."""
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
    """Initialize the logging. """
    zrlog.init_logging()


def load_object(obj_name: str) -> t.Any:
    """Imports an object from a string"""
    # obj_name should something like package.subpackage.object_name
    package_dot_pos = obj_name.rfind(".")
    package = obj_name[0:package_dot_pos]
    specific_cls_name = obj_name[package_dot_pos + 1:]
    mod = importlib.import_module(package)
    return getattr(mod, specific_cls_name)


class BaseThread(threading.Thread):
    """Provides common tools for threads that get run from a master controller."""

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, log_name: str, loop_delay: float = 0.25, is_daemon: bool = True):
        super().__init__()
        self._log = logging.getLogger(log_name)
        self._halt = threading.Event()
        self._loop_delay = loop_delay
        self.daemon = is_daemon
        self._metric_results = None

    def terminate(self):
        """Terminate the thread by setting the event.

        Callers should then use join() to wait for the current run to finish.
        """
        self._halt.set()

    def set_run_metric(self, metric_success: "erddaputil.main.metrics.AbstractMetric", metric_failure: "erddaputil.main.metrics.AbstractMetric", cb: str):
        """Set the success and failure metrics as given, along with a callback to call."""
        self._metric_results = (metric_success, metric_failure, cb)

    @injector.as_thread_run
    def run(self):
        try:
            self._setup()

            while not self._halt.is_set():
                result = None
                start_time = timeit.default_timer()
                try:
                    result = self._run()
                except (KeyboardInterrupt, SystemExit) as ex:
                    result = None
                    raise ex
                except Exception as ex:
                    self._log.exception(ex)
                    result = False
                finally:
                    end_time = timeit.default_timer()
                    if self._metric_results and result is not None:
                        metric = self._metric_results[0] if result else self._metric_results[1]
                        getattr(metric, self._metric_results[2])(max(end_time - start_time, 0.0))
                self._sleep(self._loop_delay)

        finally:
            self._cleanup()

    def _sleep(self, time: float):
        """Sleep for a given time but use the halt event."""
        if time > 0:
            self._halt.wait(time)

    def _run(self) -> t.Optional[bool]:
        """In-loop execution, returns True/False if success or None if the run was aborted and shouldn't be tracked."""
        raise NotImplementedError()

    def _setup(self):
        """Pre-execution when thread is starting."""
        pass

    def _cleanup(self):
        """Cleanup when thread is exiting."""
        pass
