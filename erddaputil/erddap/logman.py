"""ERDDAP Log Management tools"""
import datetime
import os
import time
from erddaputil.common import BaseThread
from erddaputil.main.metrics import ScriptMetrics
from autoinject import injector


class ErddapLogManager(BaseThread):

    metrics: ScriptMetrics = None

    @injector.construct
    def __init__(self):
        super().__init__("erddaputil.logman")
        self.bpd = self.config.as_path(("erddaputil", "erddap", "big_parent_directory"))
        self._log_path = None
        if self.bpd is None or not self.bpd.exists():
            self._log.warning("ERDDAP base directory not properly set")
            self.bpd = None
        else:
            self._log_path = self.bpd / "logs"
        self.log_retention_days = self.config.as_int(("erddaputil", "logman", "retention_days"), default=31)
        self.log_file_prefixes = self.config.get(
            ("erddaputil", "logman", "file_prefixes"),
            default=["logPreviousArchivedAt", "logArchivedAt", "emailLog"]
        )
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
        if self.bpd is None or not self.log_file_prefixes:
            return False
        if self._log_path is None or not self._log_path.exists():
            return False
        self._log.info(f"Checking for old log files")
        count = 0
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=self.log_retention_days)).timestamp()
        for file in os.scandir(self._log_path):
            if any(file.name.startswith(x) for x in self.log_file_prefixes) and file.stat().st_mtime < cutoff:
                self._log.notice(f"Removing {file.path}")
                os.unlink(file.path)
                count += 1
        self.metrics.counter("erddaputil_logman_log_files_removed", description='Number of old log files removed').inc(count)
        return True
