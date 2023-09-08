"""Shared utilities."""
import threading
from autoinject import injector
import zirconium as zr
import zrlog
import pathlib
import os
import importlib
import timeit
import typing as t
import signal

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
    app.register_environ_map({
        "ERDDAPUTIL_SECRET_KEY": ("erddaputil", "secret_key"),
        "ERDDAPUTIL_USE_LOCAL_DAEMON": ("erddaputil", "use_local_daemon"),
        "ERDDAPUTIL_USE_AMPQ_EXCHANGE": ("erddaputil", "use_ampq_exchange"),
        "ERDDAPUTIL_METRICS_MANAGER": ("erddaputil", "metrics_manager"),
        "ERDDAPUTIL_COMPILE_ON_BOOT": ("erddaputil", "compile_on_boot"),
        "ERDDAPUTIL_CREATE_DEFAULT_USER_ON_BOOT": ("erddaputil", "create_default_user_on_boot"),
        "ERDDAPUTIL_DEFAULT_USERNAME": ("erddaputil", "default_username"),
        "ERDDAPUTIL_DEFAULT_PASSWORD": ("erddaputil", "default_password"),
        "ERDDAPUTIL_ERDDAP_DATASETS_XML_TEMPLATE": ("erddaputil", "erddap", "datasets_xml_template"),
        "ERDDAPUTIL_ERDDAP_DATASETS_D": ("erddaputil", "erddap", "datasets_d"),
        "ERDDAPUTIL_ERDDAP_BIG_PARENT_DIRECTORY": ("erddaputil", "erddap", "big_parent_directory"),
        "ERDDAPUTIL_ERDDAP_DATASETS_XML": ("erddaputil", "erddap", "datasets_xml"),
        "ERDDAPUTIL_ERDDAP_BASE_URL": ("erddaputil", "erddap", "base_url"),
        "ERDDAPUTIL_ERDDAP_SUBSCRIPTION_BLOCK_LIST": ("erddaputil", "erddap", ",subscription_block_list"),
        "ERDDAPUTIL_ERDDAP_IP_BLOCK_LIST": ("erddaputil", "erddap", ",ip_block_list"),
        "ERDDAPUTIL_ERDDAP_UNLIMITED_ALLOW_LIST": ("erddaputil", "erddap", ",unlimited_allow_list"),
        "ERDDAPUTIL_DATASET_MANAGER_MAX_PENDING": ("erddaputil", "dataset_manager", ",max_pending"),
        "ERDDAPUTIL_DATASET_MANAGER_MAX_DELAY_SECONDS": ("erddaputil", "dataset_manager", ",max_delay_seconds"),
        "ERDDAPUTIL_DATASET_MANAGER_MAX_RECOMPILE_DELAY": ("erddaputil", "dataset_manager", ",max_recompile_delay"),
        "ERDDAPUTIL_DATASET_MANAGER_SKIP_MISCONFIGURED_DATASETS": ("erddaputil", "dataset_manager", ",skip_misconfigured_datasets"),
        "ERDDAPUTIL_DATASET_MANAGER_BACKUPS": ("erddaputil", "dataset_manager", ",backups"),
        "ERDDAPUTIL_DATASET_MANAGER_BACKUP_RETENTION_DAYS": ("erddaputil", "dataset_manager", ",backup_retention_days"),
        "ERDDAPUTIL_DAEMON_HOST": ("erddaputil", "daemon", ",host"),
        "ERDDAPUTIL_DAEMON_PORT": ("erddaputil", "daemon", ",port"),
        "ERDDAPUTIL_SERVICE_HOST": ("erddaputil", "service", ",host"),
        "ERDDAPUTIL_SERVICE_PORT": ("erddaputil", "service", ",port"),
        "ERDDAPUTIL_SERVICE_BACKLOG": ("erddaputil", "service", ",backlog"),
        "ERDDAPUTIL_SERVICE_LISTEN_BLOCK_SECONDS": ("erddaputil", "service", ",listen_block_seconds"),
        "ERDDAPUTIL_LOGMAN_ENABLED": ("erddaputil", "logman", ",enabled"),
        "ERDDAPUTIL_LOGMAN_RETENTION_DAYS": ("erddaputil", "logman", ",retention_days"),
        "ERDDAPUTIL_LOGMAN_SLEEP_TIME_SECONDS": ("erddaputil", "logman", ",sleep_time_seconds"),
        "ERDDAPUTIL_LOGMAN_INCLUDE_TOMCAT": ("erddaputil", "logman", "include_tomcat"),
        "ERDDAPUTIL_AMPQ_CLUSTER_NAME": ("erddaputil", "ampq", ",cluster_name"),
        "ERDDAPUTIL_AMPQ_HOSTNAME": ("erddaputil", "ampq", ",hostname"),
        "ERDDAPUTIL_AMPQ_CONNECTION": ("erddaputil", "ampq", ",connection"),
        "ERDDAPUTIL_AMPQ_EXCHANGE_NAME": ("erddaputil", "ampq", ",exchange_name"),
        "ERDDAPUTIL_AMPQ_CREATE_QUEUE": ("erddaputil", "ampq", ",create_queue"),
        "ERDDAPUTIL_AMPQ_IMPLEMENTATION": ("erddaputil", "ampq", ",implementation"),
        "ERDDAPUTIL_WEBAPP_ENABLE_METRICS_COLLECTOR": ("erddaputil", "webapp", ",enable_metrics_collector"),
        "ERDDAPUTIL_WEBAPP_ENABLE_MANAGEMENT_API": ("erddaputil", "webapp", ",enable_management_api"),
        "ERDDAPUTIL_WEBAPP_PASSWORD_FILE": ("erddaputil", "webapp", ",password_file"),
        "ERDDAPUTIL_WEBAPP_PASSWORD_HASH": ("erddaputil", "webapp", ",password_hash"),
        "ERDDAPUTIL_WEBAPP_SALT_LENGTH": ("erddaputil", "webapp", ",salt_length"),
        "ERDDAPUTIL_WEBAPP_MIN_ITERATIONS": ("erddaputil", "webapp", ",min_iterations"),
        "ERDDAPUTIL_WEBAPP_ITERATIONS_JITTER": ("erddaputil", "webapp", ",iterations_jitter"),
        "ERDDAPUTIL_LOCALPROM_HOST": ("erddaputil", "localprom", ",host"),
        "ERDDAPUTIL_LOCALPROM_PORT": ("erddaputil", "localprom", ",port"),
        "ERDDAPUTIL_LOCALPROM_METRICS_PATH": ("erddaputil", "localprom", ",metrics_path"),
        "ERDDAPUTIL_LOCALPROM_USERNAME": ("erddaputil", "localprom", ",username"),
        "ERDDAPUTIL_LOCALPROM_PASSWORD": ("erddaputil", "localprom", ",password"),
        "ERDDAPUTIL_LOCALPROM_MAX_TASKS": ("erddaputil", "localprom", ",max_tasks"),
        "ERDDAPUTIL_LOCALPROM_BATCH_SIZE": ("erddaputil", "localprom", ",batch_size"),
        "ERDDAPUTIL_LOCALPROM_BATCH_WAIT_SECONDS": ("erddaputil", "localprom", ",batch_wait_seconds"),
        "ERDDAPUTIL_LOCALPROM_MAX_RETRIES": ("erddaputil", "localprom", ",max_retries"),
        "ERDDAPUTIL_LOCALPROM_RETRY_DELAY_SECONDS": ("erddaputil", "localprom", ",retry_delay_seconds"),
        "ERDDAPUTIL_LOCALPROM_DELAY_SECONDS": ("erddaputil", "localprom", ",delay_seconds"),
        "ERDDAPUTIL_STATUS_SCRAPER_MEMORY_PATH": ("erddaputil", "status_scraper", "memory_path"),
        "ERDDAPUTIL_STATUS_SCRAPER_ENABLED": ("erddaputil", "status_scraper", "enabled"),
        "ERDDAPUTIL_STATUS_SCRAPER_SLEEP_TIME_SECONDS": ("erddaputil", "status_scraper", "sleep_time_seconds"),
        "ERDDAPUTIL_SHOW_CONFIG": ("erddaputil", "show_config"),
        "ERDDAPUTIL_FIX_ERDDAP_BPD_PERMISSIONS": ("erddaputil", "fix_erddap_bpd_permissions"),
        "ERDDAPUTIL_TOMCAT_UID": ("erddaputil", "tomcat", "uid"),
        "ERDDAPUTIL_TOMCAT_GID": ("erddaputil", "tomcat", "gid"),
        "ERDDAPUTIL_TOMCAT_LOG_DIRECTORY": ("erddaputil", "tomcat", "log_directory"),
        "ERDDAPUTIL_TOMCAT_LOG_PATTERN": ("erddaputil", "tomcat", "log_pattern"),
        "ERDDAPUTIL_TOMCAT_LOG_PREFIX": ("erddaputil", "tomcat", "log_prefix"),
        "ERDDAPUTIL_TOMCAT_LOG_SUFFIX": ("erddaputil", "tomcat", "log_suffix"),
        "ERDDAPUTIL_TOMCAT_LOG_ENCODING": ("erddaputil", "tomcat", "log_encoding"),
        "ERDDAPUTIL_TOMCAT_MAJOR_VERSION": ("erddaputil", "tomcat", "major_version"),
        "ERDDAPUTIL_TOMTAIL_MEMORY_FILE": ("erddaputil", "tomtail", "memory_file"),
        "ERDDAPUTIL_TOMTAIL_OUTPUT_FILE": ("erddaputil", "tomtail", "output_file"),
        "ERDDAPUTIL_TOMTAIL_OUTPUT_PATTERN": ("erddaputil", "tomtail", "output_pattern"),
        "ERDDAPUTIL_TOMTAIL_ENABLED": ("erddaputil", "tomtail", "enabled"),
        "ERDDAPUTIL_TOMTAIL_SLEEP_TIME_SECONDS": ("erddaputil", "tomtail", "sleep_time_seconds"),


    })


def init_config():
    """Initialize the logging. """
    zrlog.init_logging()
    _print_config()


@injector.inject
def _print_config(cfg: zr.ApplicationConfig = None):
    if cfg.as_bool(("erddaputil", "show_config"), default=False):
        zr.print_config(obfuscate_keys=[
            ("erddaputil", "secret_key"),
            ("erddaputil", "default_password"),
            ("erddaputil", "localprom", "password"),
            ("erddaputil", "webapp", "peppers"),
        ])


def load_object(obj_name: str) -> t.Any:
    """Imports an object from a string"""
    # obj_name should something like package.subpackage.object_name
    package_dot_pos = obj_name.rfind(".")
    package = obj_name[0:package_dot_pos]
    specific_cls_name = obj_name[package_dot_pos + 1:]
    mod = importlib.import_module(package)
    return getattr(mod, specific_cls_name)


class BaseApplication:

    def __init__(self, log_name):
        init_config()
        self._log = zrlog.get_logger(log_name)
        self._halt = threading.Event()
        self._break_count = 0

    def sig_handle(self, sig_num, frame):
        """Handle signals."""
        self._log.info(f"Signal {sig_num} caught, halting")
        self._halt.set()
        self._break_count += 1
        if self._break_count >= 3:
            self._log.critical(f"Program halting unexpectedly")
            raise KeyboardInterrupt()

    def _register_halt_signal(self, sig_name):
        if hasattr(signal, sig_name):
            signal.signal(getattr(signal, sig_name), self.sig_handle)

    def _startup(self):
        self._register_halt_signal("SIGINT")
        self._register_halt_signal("SIGTERM")
        self._register_halt_signal("SIGBREAK")
        self._register_halt_signal("SIGQUIT")

    def _shutdown(self):
        pass

    def run_forever(self):
        self._log.notice("Starting")
        try:
            self._startup()
            while not self._halt.is_set():
                self._run()
        except Exception:
            self._log.exception("Error during execution")
        finally:
            self._log.notice("Shutting down")
            self._shutdown()

    def _run(self):
        self._halt.wait(0.5)


class BaseThread(threading.Thread):
    """Provides common tools for threads that get run from a master controller."""

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, log_name: str, loop_delay: float = 1, is_daemon: bool = False):
        super().__init__()
        self._log = zrlog.get_logger(log_name)
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
            self._log.trace("starting thread setup")
            self._setup()
            self._log.trace("starting main thread loop")
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
            self._log.trace("cleaning up thread")
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
