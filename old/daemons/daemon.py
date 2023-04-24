import logging
import queue
import threading

import clusterman.cli.app
import zirconium as zr
from autoinject import injector
from erddaputil.main.metrics import ScriptMetrics
from old.util.common import load_object
from clusterman.main.controller import SyncController
import signal


class ErddapUtilError(Exception):

    def __init__(self, message, original_exception=None):
        super().__init__(message)
        self.original_exception = original_exception


class ErddapManagementDaemon:

    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, daemon_classes: dict, check_interval: int = None, with_sync: bool = True):
        self.daemon_classes = daemon_classes
        if with_sync:
            self.add_sync_daemons()
        self.log = logging.getLogger("erddaputil.daemon")
        self._sync_app = None
        self._sync_queue = None
        self._executing_threads = {}
        self._halt = threading.Event()
        self._recheck_interval = 1
        auto_enable = self.cfg.get(("erddaputil", "daemon", "auto_enable"), default=[]) or []
        for daemon_name in auto_enable:
            if daemon_name not in self.daemon_classes:
                self.daemon_classes[daemon_name] = auto_enable[daemon_name]
        disabled = self.cfg.get(("erddaputil", "daemon", "disabled_daemons"), default=[]) or []
        for daemon_name in disabled:
            if daemon_name in self.daemon_classes:
                self.daemon_classes[daemon_name] = False
        for daemon_name in [str(x) for x in self.daemon_classes.keys()]:
            if self.daemon_classes[daemon_name] is False or self.daemon_classes[daemon_name] is None:
                del self.daemon_classes[daemon_name]
        if not self.daemon_classes:
            raise ValueError("No daemons are configured to run")

    @injector.inject
    def add_sync_daemons(self, sync_controller: SyncController = None):
        self._sync_app = clusterman.cli.app.create_app()
        self._sync_queue = queue.SimpleQueue()
        with self._sync_app.app_context():
            sync_controller.create_databases()
        if self.cfg.is_truthy(("clusterman", "ampq", "broker_uri")):
            self.daemon_classes["sync_ampq"] = ("clusterman.main.aqmp.MessageQueueListener", [self._sync_app])
        self.daemon_classes["sync_cli"] = ("clusterman.main.mainline.MainListener", [self._sync_app])
        self.daemon_classes["sync_refresh"] = ("clusterman.main.processing.RefreshController", [self._sync_app])
        self.daemon_classes["sync_processor"] = ("clusterman.main.processing.FileSyncController", [self._sync_app])
        self.daemon_classes["sync_manager"] = ("erddaputil.daemons.sync.ErddapSyncManager", [self._sync_queue])
        sync_controller.add_result_queue(self._sync_queue)

    def _get_daemon_obj(self, obj_def):
        args = []
        kwargs = {}
        if isinstance(obj_def, tuple):
            obj_cls = obj_def[0]
            args = (obj_def[1] or []) if len(obj_def) > 1 else []
            kwargs = (obj_def[2] or {}) if len(obj_def) > 2 else {}
        else:
            obj_cls = obj_def
        if isinstance(obj_cls, str):
            return load_object(obj_cls)(*args, **kwargs)
        else:
            return obj_cls(*args, **kwargs)

    def halt(self, *args, **kwargs):
        self._halt.set()
        for daemon_name in self._executing_threads:
            if self._executing_threads[daemon_name].is_alive():
                self._executing_threads[daemon_name].halt()

    @injector.inject
    def run_forever(self, metrics: ScriptMetrics = None):
        if not self.daemon_classes:
            return
        signal.signal(signal.SIGINT, self.halt)
        try:
            self._boot_daemons()
            while not self._halt.is_set():
                self._boot_daemons()
                self._halt.wait(self._recheck_interval)
        except Exception as ex:
            self.log.exception(ex)
        finally:
            self.halt()
        for daemon_name in self._executing_threads:
            self._executing_threads[daemon_name].join()
        metrics.halt()

    def _boot_daemons(self):
        for daemon_name in self.daemon_classes:
            if daemon_name in self._executing_threads and self._executing_threads[daemon_name].is_alive():
                continue
            if daemon_name not in self._executing_threads:
                self.log.info(f"Starting daemon {daemon_name}")
            else:
                self.log.warning(f"Restarting daemon {daemon_name}")
            self._executing_threads[daemon_name] = self._get_daemon_obj(self.daemon_classes[daemon_name])
            self._executing_threads[daemon_name].start()

    @staticmethod
    @injector.inject
    def run_once(daemon_cls, metrics: ScriptMetrics = None):
        try:
            daemon = daemon_cls(True)
            daemon.run_once(do_cleanup=True)
        finally:
            metrics.halt()


class ErddapUtil(threading.Thread):

    config: zr.ApplicationConfig = None
    metrics: ScriptMetrics = None

    @injector.construct
    def __init__(self, util_name: str, raise_error: bool = True, default_sleep_time: int = 1):
        super().__init__()
        self.log = logging.getLogger(f"erddaputil.{util_name}")
        self._raise_error = raise_error
        self.metric_prefix = f"erddaputil_{util_name}"
        self._error_counter = self.metrics.counter(f"{self.metric_prefix}_errors_total", {"level": "error"})
        self._warning_counter = self.metrics.counter(f"{self.metric_prefix}_errors_total", {"level": "warning"})
        self._success_counter = self.metrics.counter(f"{self.metric_prefix}_executions_total", {"result": "success"})
        self._failure_counter = self.metrics.counter(f"{self.metric_prefix}_executions_total", {"result": "failure"})
        self._interrupt_counter = self.metrics.counter(f"{self.metric_prefix}_executions_total", {"result": "interrupted"})
        self._has_been_init = False
        self.daemon = True
        self._halt = threading.Event()
        self.wait_time = self.config.as_int(("erddaputil", util_name, "wait_time_seconds"), default=default_sleep_time)

    def log_or_raise(self, message: str, exc_cls: type = None, original: Exception = None):
        self._error_counter.increment()
        if self._raise_error:
            if original is not None:
                raise ErddapUtilError(message, original)
            elif exc_cls is not None:
                raise ErddapUtilError(message, exc_cls(message))
            else:
                raise ErddapUtilError(message, ValueError(message))
        else:
            self.log.error(message)

    def halt(self):
        self._halt.set()

    @injector.as_thread_run
    def run(self):
        try:
            while not self._halt:
                try:
                    self.run_once(False)
                    self._halt.wait(self.wait_time)
                except (SystemExit, KeyboardInterrupt, NotImplementedError) as ex:
                    raise ex
        finally:
            self._cleanup()

    def run_once(self, do_cleanup: bool = True):
        result = False
        was_interrupted = False
        try:
            if not self._has_been_init:
                self._has_been_init = True
                self._init()
            # Extra check for breaking here
            if self._halt.set():
                return
            result = self._run()
        except ErddapUtilError as ex:
            # These have already been logged
            raise ex
        except (SystemExit, KeyboardInterrupt) as ex:
            self._interrupt_counter.increment()
            was_interrupted = True
            raise ex
        except Exception as ex:
            self.log_or_raise(str(ex), original=ex)
        finally:
            if was_interrupted:
                pass
            elif result is False:
                self._failure_counter.increment()
            else:
                self._success_counter.increment()
            if do_cleanup:
                self._cleanup()

    def _init(self):
        pass

    def _run(self, *args, **kwargs):
        raise NotImplementedError()

    def _cleanup(self):
        pass
