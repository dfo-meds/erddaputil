"""ERDDAP Log Management tools"""
import datetime
import os
import time
from erddaputil.common import BaseThread
from erddaputil.main.metrics import ScriptMetrics
from autoinject import injector


class LogFileDirectory:

    def __init__(self, base_directory, file_criteria):
        self.directory = base_directory
        self.criteria = file_criteria

class ErddapLogManager(BaseThread):

    metrics: ScriptMetrics = None

    @injector.construct
    def __init__(self):
        super().__init__("erddaputil.logman")
        self._log_check_list = []

        # Tomtail output files
        if self.config.as_bool(("erddaputil", "logman", "include_tomtail"), default=True):
            tomtail_output = self.config.as_path(("erddaputil", "tomtail", "output_directory"), default=None)
            tomtail_pattern = self.config.as_str(("erddaputil", "tomtail", "output_pattern"), default="erddap_access_logs_%Y%m%d.log")
            if tomtail_output and tomtail_output.parent.exists():
                prefix = tomtail_pattern[0:tomtail_pattern.find('%')] if '%' in tomtail_pattern else ''
                suffix = tomtail_pattern[tomtail_pattern.rfind('.'):] if '.' in tomtail_pattern else ''
                self._log_check_list.append(
                    LogFileDirectory(tomtail_output, [{"prefix": prefix, "suffix": suffix}])
                )
                self._log.info(f"Tomtail log file management enabled")
            else:
                self._log.info(f"Tomtail log file management disabled, no output directory present")
        else:
            self._log.info(f"Tomtail log file management disabled")

        # Tomcat log files
        if self.config.as_bool(("erddaputil", "logman", "include_tomcat"), default=False):
            tomcat_logs = self.config.as_path(("erddaputil", "tomcat", "log_directory"), default=None)
            tomcat_log_prefix = self.config.as_str(("erddaputil", "tomcat", "log_prefix"), default="access_log")
            tomcat_log_suffix = self.config.as_str(("erddaputil", "tomcat", "log_suffix"), default="")
            if tomcat_logs is None:
                self._log.warning("Tomcat log directory not specified, log file management disabled")
            else:
                self._log_check_list.append(LogFileDirectory(tomcat_logs, [{"prefix": tomcat_log_prefix, "suffix": tomcat_log_suffix}]))
                self._log.info("Tomcat log file management enabled")
        else:
            self._log.info("Tomcat log file management disabled")

        # ERDDAP log files
        if self.config.as_bool(("erddaputil", "logman", "include_erddap"), default=True):
            bpd = self.config.as_path(("erddaputil", "erddap", "big_parent_directory"), default=None)
            erddap_file_prefixes = self.config.get(
                ("erddaputil", "logman", "file_prefixes"),
                default=["logPreviousArchivedAt", "logArchivedAt", "emailLog"]
            )
            if not bpd:
                self._log.warning("ERDDAP base directory not properly set, log file management disabled")
            else:
                self._log_check_list.append(LogFileDirectory(bpd / "logs", [{"prefix": p} for p in erddap_file_prefixes]))
                self._log.info("ERDDAP log file management enabled")
        else:
            self._log.info("ERDDAP log file management disabled")

        # Global stuff
        self.log_retention_days = self.config.as_int(("erddaputil", "logman", "retention_days"), default=31)
        self.run_frequency = self.config.as_int(("erddaputil", "logman", "sleep_time_seconds"), default=3600)
        self.enabled = self.config.as_bool(("erddaputil", "logman", "enabled"), default=True)
        self._last_run = None
        self.set_run_metric(
            self.metrics.summary('erddaputil_logman_runs', labels={'result': 'success'}),
            self.metrics.summary('erddaputil_logman_runs', labels={'result': 'failure'}),
            'observe'
        )

    def _run(self, *args, **kwargs):
        if not self.enabled:
            return None
        if self._last_run is not None and (time.monotonic() - self._last_run) < self.run_frequency:
            return None
        self._last_run = time.monotonic()
        self._log.info(f"Cleaning up old log files")
        count = 0
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=self.log_retention_days)).timestamp()
        for ldf in self._log_check_list:
            if ldf.directory.exists():
                self._log.debug(f"Cleaning up {ldf.directory}")
                for file in os.scandir(ldf.directory):
                    if not any(self._matches_criteria(file.name, x) for x in ldf.criteria):
                        continue
                    if file.stat().st_mtime < cutoff:
                        self._log.notice(f"Removing log file {file.path}")
                        os.unlink(file.path)
                        count += 1
            else:
                self._log.info(f"Skipping {ldf.directory}, does not exist")
        self.metrics.counter("erddaputil_logman_log_files_removed", description='Number of old log files removed').inc(count)
        self._log.debug(f"Log file cleanup complete, [{count}] entries removed")
        return True

    def _matches_criteria(self, filename, criteria):
        if 'prefix' in criteria and criteria['prefix'] and not filename.startswith(criteria['prefix']):
            return False
        if 'suffix' in criteria and criteria['suffix'] and not filename.endswith(criteria['suffix']):
            return False
        return True
