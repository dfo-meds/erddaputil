import datetime
import os
import time
from erddaputil.common import BaseThread


class ErddapLogManager(BaseThread):

    def __init__(self):
        super().__init__("erddaputil.logman", 15)
        self.bpd = self.config.as_path(("erddaputil", "erddap", "big_parent_directory"))
        if self.bpd is None or not self.bpd.exists():
            self._log.warning("ERDDAP base directory not properly set")
            self.bpd = None
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
        if self._last_run is not None and (time.monotonic() - self._last_run) < self.run_frequency:
            return None
        cutoff = datetime.datetime.now() - datetime.timedelta(days=self.log_retention_days)
        for file in os.scandir(self.bpd / "logs"):
            if file.stat().m_time < cutoff and any(file.name.startswith(x) for x in self.log_file_prefixes):
                file.unlink()
        return True
