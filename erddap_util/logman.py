import datetime
import os
from .daemon import ErddapUtil


class ErddapLogManager(ErddapUtil):

    def __init__(self, raise_error: bool = False):
        super().__init__("logman", raise_error, 14400)
        self.erddap_directory = None
        self.log_retention_days = None
        self.log_path = None
        self._logs_cleaned_counter = self.metrics.counter(f"{self.metric_prefix}_log_files_removed_count")
        self._log_tokens = []

    def _init(self):
        self.erddap_directory = self.config.as_path(("erddaputil", "big_parent_dir"))
        if self.erddap_directory is None or not self.erddap_directory.exists():
            self.erddap_directory = None
            self.log_or_raise(f"ERDDAP's big parent directory not found: {self.erddap_directory}")
        self.log_retention_days = self.config.as_str(("erddaputil", "logman", "retention_days"), default="31")
        if not self.log_retention_days.isdigit():
            self.log_retention_days = 31
            self.log_or_raise(f"Log retention days must be a positive integer: {self.log_retention_days}")
        else:
            self.log_retention_days = int(self.log_retention_days)
        self.log_path = self.erddap_directory / "logs" if self.erddap_directory else None
        self._log_tokens = self.config.get(
            ("erddaputil", "logman", "log_file_prefixes"),
            default=["logPreviousArchivedAt", "logArchivedAt", "emailLog"]
        )
        if not self._log_tokens:
            self.log.warning(f"No log prefixes defined")
            self._warning_counter.increment()
        elif isinstance(self._log_tokens, str):
            self._log_tokens = [self._log_tokens]

    def _run(self, *args, **kwargs):
        if self.log_path is None:
            self._warning_counter.increment()
            self.log.warning(f"Log path not defined, make sure big_parent_dir is set properly")
            return False
        if not self.log_path.exists():
            self._warning_counter.increment()
            self.log.warning(f"Log directory doesn't exist: {self.log_path}")
            return False
        if not self.log_path.is_dir():
            self._warning_counter.increment()
            self.log.warning(f"Log directory is not a directory: {self.log_path}")
            return False
        if not self._log_tokens:
            return True
        cutoff = datetime.datetime.now() - datetime.timedelta(days=self.log_retention_days)
        self.log.out(f"Removing ERDDAP archived log files from before {cutoff} in directory {self.log_path}")
        count_removed = 0
        for file in os.scandir(self.log_path):
            if file.stat().m_time < cutoff and any(file.name.startswith(x) for x in self._log_tokens):
                self.log.info(f"Removing archived log file {file.path}")
                count_removed += 1
                file.unlink()
        self._logs_cleaned_counter.increment(count_removed)
        return True
