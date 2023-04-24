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
        super().__init__("erddaputil.logman", 15)
        self.bpd = self.config.as_path(("erddaputil", "erddap", "big_parent_directory"))
        self._log_ath = None
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

    def _run(self, *args, **kwargs):
        if not self.enabled:
            return None
        if self.bpd is None or not self.log_file_prefixes:
            return False
        if self._log_path is None or not self._log_path.exists():
            return False
        if self._last_run is not None and (time.monotonic() - self._last_run) < self.run_frequency:
            return None

        count = 0
        cutoff = datetime.datetime.now() - datetime.timedelta(days=self.log_retention_days)
        for file in os.scandir(self._log_path):
            if file.stat().m_time < cutoff and any(file.name.startswith(x) for x in self.log_file_prefixes):
                file.unlink()
                count += 1
        self.metrics.counter("erddaputil_logs_cleared").increment(count)
        return True
