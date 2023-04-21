import hashlib
from .daemon import ErddapUtil
from graceful_shutdown import ShutdownProtection
import pathlib
import typing as t
import datetime


class ErddapLogTail(ErddapUtil):

    def __init__(self, raise_error: bool = False):
        super().__init__("logtail", raise_error, 5)
        self.erddap_directory = None
        self._files_tailed = {}
        self._logs_tailed = self.metrics.counter(f"{self.metric_prefix}_logs_tailed_bytes")
        self._target_dir: t.Optional[pathlib.Path] = None
        self._info_file = None
        self._log_file_info = {}
        self._chunk_size = self.config.as_int(("erddaputil", "logtail", "chunk_size"), default=1000)
        self._batch_size = self.config.as_int(("erddaputil", "logtail", "batch_size"), default=10000)
        self._default_min_size = self.config.as_int(("erddaputil", "logtail", "min_size_for_hash"), default=1000)
        self._default_take_size = self.config.as_int(("erddaputil", "logtail", "read_size_for_hash"), default=10000)
        self._buffer_size = self.config.as_int(("erddaputil", "logtail", "buffer_size"), default=20000)

    def _init(self):
        self.erddap_directory = self.config.as_path(("erddaputil", "big_parent_dir"))
        if self.erddap_directory is None or not self.erddap_directory.exists():
            self.erddap_directory = None
            self.log_or_raise(f"ERDDAP's big parent directory not found: {self.erddap_directory}")
        else:
            log_path = self.erddap_directory / "logs"
            self._files_tailed["erddap_log"] = (log_path / "log.txt", log_path / "log.txt.previous")
        self._target_dir = self.config.as_path(("erddaputil", "logtail", "output_dir"))
        if self._target_dir and (not self._target_dir.exists()) and self._target_dir.parent.exists():
            self._target_dir.mkdir()
        if not self._target_dir or not self._target_dir.exists():
            self.log_or_raise(f"Output directory {self._target_dir} not found")
            self._target_dir = None
        else:
            self._info_file = self._target_dir / ".log_info"
            if self._info_file.exists():
                with open(self._info_file, "r") as h:
                    for line in h.readlines():
                        line = line.strip("\r\n\t ")
                        if line:
                            pieces = line.split("|")
                            self._log_file_info[pieces[0]] = pieces[1:]

    def _save_log_file_info(self):
        with open(self._info_file, "w") as h:
            for key in self._log_file_info:
                h.write(f"{key}|{'|'.join(self._log_file_info[key])}\n")

    def _run(self, *args, **kwargs):
        if not self._target_dir:
            self.log.warning("Output directory not configured")
            return False
        if not self._files_tailed:
            self.log.warning("ERDDAP directory not configured properly")
            return False
        for file_key in self._files_tailed:
            self._tail_logs(file_key, *self._files_tailed[file_key])
        return True

    def _tail_logs(self, file_key, src_file, prev_file):
        if file_key not in self._log_file_info:
            self._log_file_info[file_key] = [0, "", 0]

        with open(src_file, "rb", buffering=0) as h:
            # Find the file size
            h.seek(0, 2)
            file_size = h.tell()
            # Reset our position
            h.seek(0, 0)

            # If this isn't the first time we've seen this file, we need to check for rotations
            if self._log_file_info[file_key][1]:
                has_rotated = False

                # If the file is smaller, we have a new file, handle the rotation
                if file_size < self._log_file_info[file_key][0]:
                    has_rotated = True

                # Also make sure the fingerprint of the first X characters is the same, otherwise handle the rotation
                elif not hashlib.sha1(h.read(self._log_file_info[file_key][2])).hexdigest() == self._log_file_info[file_key][1]:
                    has_rotated = True

                # Handle the rotation
                if has_rotated:
                    try:
                        # This lets us use a callable to get the previous file name
                        pf = prev_file if not callable(prev_file) else prev_file()
                        with open(pf, "r") as h2:
                            self._tail_file(h2, file_key)
                        # Reset hash first to deal with the current file as a fresh one even if we are interrupted
                        self._log_file_info[file_key][1] = ""
                        self._log_file_info[file_key][0] = 0
                        self._log_file_info[file_key][2] = 0
                    finally:
                        self._save_log_file_info()

            # First time reading the file, generate a fingerprint
            if not self._log_file_info[file_key][1]:
                if file_size >= self._default_min_size:
                    self._log_file_info[file_key][0] = 0
                    self._log_file_info[file_key][1] = hashlib.sha1(h.read(self._default_take_size)).hexdigest()
                    self._log_file_info[file_key][2] = h.tell()
                    h.seek(0, 0)
                else:
                    return  # Wait for there to be more data

            # Copy the current contents
            self._tail_file(h, file_key)

    def _tail_file(self, fd, file_key: str):
        fd.seek(self._log_file_info[file_key][0], 0)
        buffer_file = self._target_dir / f".{file_key}.buffer"
        with ShutdownProtection(5) as pb:
            count_bytes = 0
            try:
                buffer_file_size = 0
                with open(buffer_file, "ab") as h:

                    pb.allow_break(True)

                    # Keep reading as long as there is new data in the original log file
                    chunk = fd.read(self._chunk_size)
                    while chunk:

                        # Writing and updating the position have to be atomic
                        count_bytes += len(chunk)
                        h.write(chunk)
                        self._log_file_info[file_key][0] = fd.tell()

                        # Limit the amount we handle in one batch
                        if count_bytes >= self._batch_size:
                            break

                        # We allow KeyboardInterrupt to occur in between reading chunks
                        # to make sure that, if we are interrupted, then the chunk is
                        # not lost.
                        pb.allow_break(True)

                        # Prepare the next chunk
                        chunk = fd.read(self._chunk_size)

                    # Update the size of the buffer file
                    buffer_file_size = h.tell()

                # Rotation of our own buffer file
                pb.allow_break(True)
                if buffer_file_size > self._buffer_size:
                    target_file = self._target_dir / f"{file_key}.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.log"
                    buffer_file.rename(target_file)
                    with open(self._target_dir / f".{file_key}.buffer", "w") as h:
                        pass
            finally:
                # We capture the state to disk here so we don't lose our place
                self._save_log_file_info()
                self._logs_tailed.increment(count_bytes)
