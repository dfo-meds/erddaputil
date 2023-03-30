import logging
import threading
import time
import zirconium as zr
from autoinject import injector
from .metrics import ScriptMetrics


class ErddapUtilError(Exception):

    def __init__(self, message, original_exception=None):
        super().__init__(message)
        self.original_exception = original_exception


class ErddapManagementDaemon:

    def __init__(self, daemon_classes: dict, check_interval: int = 60):
        self.daemon_classes = daemon_classes
        self.log = logging.getLogger("erddaputil.daemon")
        self._executing_threads = {}
        self._halting = False
        self._recheck_interval = check_interval

    @injector.inject
    def start(self, metrics: ScriptMetrics = None):
        if not self.daemon_classes:
            return
        for daemon_name in self.daemon_classes:
            self.log.info(f"Starting daemon {daemon_name}")
            self._executing_threads[daemon_name] = self.daemon_classes[daemon_name](False)
            self._executing_threads[daemon_name].start()
        while not self._halting:
            try:
                for daemon_name in self._executing_threads:
                    if not self._executing_threads[daemon_name].is_alive():
                        self.log.warning(f"Restarting daemon {daemon_name}")
                        self._executing_threads[daemon_name] = self.daemon_classes[daemon_name](False)
                        self._executing_threads[daemon_name].start()
                time.sleep(self._recheck_interval)
            except (KeyboardInterrupt, SystemExit) as ex:
                self._halting = True
        for daemon_name in self._executing_threads:
            self._executing_threads[daemon_name].halt()
        for daemon_name in self._executing_threads:
            self._executing_threads[daemon_name].join()
        metrics.halt()

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
    def __init__(self, util_name: str, raise_error: bool = True, default_sleep_time:int = 5):
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
        self._break_flag = False
        self.wait_time = self.config.as_int(("erddaputil", util_name, "wait_time"), default=default_sleep_time)

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
        self._break_flag = True

    def run(self):
        try:
            while not self._break_flag:
                try:
                    self.run_once(False)
                    # this method of sleeping allows the program to break within a second as needed
                    for i in range(0, self.wait_time):
                        if self._break_flag:
                            break
                        time.sleep(1)
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
            print(was_interrupted)
            print(result)
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