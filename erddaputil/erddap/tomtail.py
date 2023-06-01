from erddaputil.common import BaseThread
import time
import os
from .parsing import ErddapLogParser, ErddapAccessLogEntry
import pathlib
import json
from autoinject import injector
import datetime
import itertools
from erddaputil.main.metrics import ScriptMetrics


DEFAULT_OUTPUT_PATTERN = "%dataset_id %request_type %s %b %T \"%U%q\""


class TomcatLogTailer(BaseThread):

    metrics: ScriptMetrics = None

    @injector.construct
    def __init__(self):
        super().__init__("erddaputil.tomtail", 5)
        self.memory_file = self.config.as_path(("erddaputil", "tomtail", "memory_file"), default=None)
        self._output_dir = self.config.as_path(("erddaputil", "tomtail", "output_directory"), default=None)
        if self._output_dir:
            if not self._output_dir.parent.exists():
                self._log.warning(f"Output file parent directory {self._output_dir} does not exist, no output will be written")
                self._output_dir = None
            elif not self._output_dir.exists():
                self._output_dir.mkdir()
        self._output_file_pattern = self.config.as_str(("erddaputil", "tomtail", "output_pattern"), default="erddap_access_logs_%Y%m%d.log")
        self._output_pattern = self.config.as_str(("erddaputil", "tomtail", "output_pattern"), default="default")
        if self._output_pattern == "default":
            self._output_pattern = DEFAULT_OUTPUT_PATTERN
        self._formatter = LogFormatter(self._output_pattern + '\n')
        if self.memory_file and not self.memory_file.parent.exists():
            self._log.warning(f"Memory file location {self.memory_file} does not exist, reverting to default")
            self.memory_file = None
        if self.memory_file is None:
            self.memory_file = pathlib.Path(".").absolute() / ".tomtail.mem"
        self._position_memory = {}
        self._load_memory_file()
        self.tomcat_logs = self.config.as_path(("erddaputil", "tomcat", "log_directory"), default=None)
        self._tomcat_log_prefix = self.config.as_str(("erddaputil", "tomcat", "log_prefix"), default="access_log")
        self._tomcat_log_suffix = self.config.as_str(("erddaputil", "tomcat", "log_suffix"), default="")
        self._tomcat_log_pattern = self.config.as_str(("erddaputil", "tomcat", "log_pattern"), default="common")
        self._tomcat_major_ver = self.config.as_int(("erddaputil", "tomcat", "major_version"), default=10)
        self._tomcat_log_encoding = self.config.as_str(("erddaputil", "tomcat", "log_encoding"), default="utf-8")
        self.run_frequency = self.config.as_int(("erddaputil", "tomtail", "sleep_time_seconds"), default=30)
        self.enabled = self.config.as_bool(("erddaputil", "tomtail", "enabled"), default=True)
        self._last_run = None
        self._batch_size = 100
        self._parser = ErddapLogParser(self._tomcat_log_pattern, self._tomcat_major_ver)

    def output_file(self):
        if self._output_dir:
            return self._output_dir / datetime.datetime.now().strftime(self._output_file_pattern)
        return None

    def _run(self):
        if not self.enabled:
            return None
        if self._last_run is not None and (time.monotonic() - self._last_run) < self.run_frequency:
            return None
        self._log.debug(f"Starting tomcat log parsing")
        self._last_run = time.monotonic()
        seen = set()
        total = 0
        if self.tomcat_logs and self.tomcat_logs.exists():
            for file in os.scandir(self.tomcat_logs):
                if self._halt.is_set():
                    break
                if not self._check_tomcat_file_name(file.name):
                    continue
                seen.add(file.path)
                total += self._check_tomcat_access_file(file.path)
        if not self._halt.is_set():
            keys = list(self._position_memory.keys())
            changed = False
            for k in keys:
                if k not in seen:
                    del self._position_memory[k]
                    changed = True
            if changed:
                self._save_memory_file()
        self._log.debug(f"Tomcat log parsing complete, found {total} records")
        return True

    def _check_tomcat_access_file(self, file_path):
        mem_key = str(file_path)
        if mem_key not in self._position_memory:
            self._log.debug(f"No record of {mem_key} found, resetting to 0")
            self._position_memory[mem_key] = 0
        with open(file_path, 'r', encoding=self._tomcat_log_encoding) as h:
            h.seek(0, 2)
            if h.tell() == self._position_memory[mem_key]:
                # No changes since last check
                return 0
            else:
                total = 0
                h.seek(self._position_memory[mem_key], 0)
                handle = None
                try:
                    file = self.output_file()
                    handle = open(file, 'a') if file else None
                    for log in self._parser.parse_chunks(h, flag=self._halt):
                        self._handle_access_log_entry(log, output=handle)
                        total += 1
                finally:
                    if handle is not None:
                        handle.close()
                    self._position_memory[mem_key] = h.tell()
                    self._save_memory_file()
                return total

    def _load_memory_file(self):
        if self.memory_file.exists():
            with open(self.memory_file, "r") as h:
                content = h.read()
                if content:
                    self._position_memory = json.loads(content)
                    self._log.debug(f"{len(self._position_memory)} entries read from tomtail memory file")
                else:
                    self._log.debug("Tomtail memory file empty")
        else:
            self._log.debug(f"Tomtail memory file {self.memory_file} does not exist")

    def _save_memory_file(self):
        self._log.debug(f"Writing tomcat tailer memory file to {self.memory_file}")
        with open(self.memory_file, 'w') as h:
            h.write(json.dumps(self._position_memory))

    def _handle_access_log_entry(self, log: ErddapAccessLogEntry, output = None):
        labels = {
            "request_type": log.request_type,
            "dataset": log.dataset_id if log.dataset_id else "-"
        }
        if log.tomcat_log.status_code() is not None:
            labels["status"] = log.tomcat_log.status_code()
        self.metrics.counter("erddap_tomcat_requests",
                             description="Requests to ERDDAP as seen by Tomcat",
                             labels=labels).inc()
        if log.tomcat_log.bytes_sent() is not None:
            self.metrics.summary("erddap_tomcat_request_bytes",
                                 description="Bytes sent by ERDDAP as seen by Tomcat (note this may be compressed)",
                                 labels=labels).observe(log.tomcat_log.bytes_sent())
        if log.tomcat_log.request_processing_time_ms() is not None:
            self.metrics.summary("erddap_tomcat_request_processing_time",
                                 description="Time to process the ERDDAP request, as logged by Tomcat",
                                 labels=labels).observe(log.tomcat_log.request_processing_time_ms() / 1000.0)
        if output:
            output.write(self._formatter.format(log))

    def _check_tomcat_file_name(self, filename):
        if self._tomcat_log_prefix and not filename.startswith(self._tomcat_log_prefix):
            return False
        if self._tomcat_log_suffix and not filename.endswith(self._tomcat_log_suffix):
            return False
        return True


class LogFormatter:

    ESCAPE_CHAR = '\\'
    ESCAPE_CHAR_ESCAPE = '\\\\'
    NEEDS_ESCAPING = ['"', '\f', '\n', '\r', '\t']
    QUOTE_TRIGGER_CHARS = [' ']
    QUOTE_CHAR = '"'

    def __init__(self, pattern: str,
                 datetime_format: str = '%Y-%m-%dT%H:%M:%S %z',
                 date_format: str = '%Y-%m-%d',
                 time_format: str = '%H:%M:%S'):
        self._pattern = pattern
        self._datetime_format = datetime_format
        self._date_format = date_format
        self._time_format = time_format

    def format(self, log: ErddapAccessLogEntry) -> str:
        output = self._pattern
        placeholders = log.placeholders()
        for key in placeholders:
            if key in output:
                output = output.replace(key, self._escape(placeholders[key]))
        return output

    def _escape(self, x) -> str:
        if isinstance(x, datetime.datetime):
            return f'[{x.strftime(self._datetime_format)}]'
        elif isinstance(x, datetime.date):
            return f'[{x.strftime(self._date_format)}]'
        elif isinstance(x, datetime.time):
            return f'[{x.strftime(self._time_format)}]'
        elif isinstance(x, int) or isinstance(x, float) or x == '-':
            return str(x)
        else:
            return self.escape(str(x))

    def escape(self, s: str) -> str:
        if not any(x in s for x in itertools.chain(self.NEEDS_ESCAPING, self.QUOTE_TRIGGER_CHARS)):
            return s
        if self.ESCAPE_CHAR in s:
            s = s.replace(self.ESCAPE_CHAR, self.ESCAPE_CHAR_ESCAPE)
        for x in self.NEEDS_ESCAPING:
            s = s.replace(x, self.ESCAPE_CHAR + x)
        return f"{self.QUOTE_CHAR}{s}{self.QUOTE_CHAR}"
