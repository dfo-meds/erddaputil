"""Manage datasets"""
from autoinject import injector
import zirconium as zr
import logging
import time


@injector.injectable_global
class ErddapDatasetManager:
    """Manages datasets on behalf of ERDDAP"""

    config: zr.ApplicationConfig = None

    HARD_FLAG = 2
    BAD_FLAG = 1
    SOFT_FLAG = 0

    @injector.construct
    def __init__(self):
        super().__init__()
        self.bpd = self.config.as_path(("erddaputil", "erddap", "big_parent_directory"))
        if not (self.bpd and self.bpd.exists()):
            raise ValueError(f"ERDDAP BPD not defined")
        self.log = logging.getLogger("erddaputil.datasets")
        self._max_pending_reloads = self.config.as_int(("erddaputil", "dataset_reloader", "max_pending"), default=2)
        self._max_reload_delay = self.config.as_int(("erddaputil", "dataset_reloader", "max_delay_seconds"), default=10)
        self._datasets_to_reload = {}

    def reload_dataset(self, dataset_id: str, flag: int = 0, flush: bool = False):
        """Queue a dataset for reloading."""
        self.log.info(f"Reload[{flag}] of {dataset_id} requested")
        if dataset_id not in self._datasets_to_reload:
            if len(self._datasets_to_reload) >= self._max_pending_reloads:
                self._flush_datasets(True)
            self._datasets_to_reload[dataset_id] = [flag, time.monotonic()]
        elif self._datasets_to_reload[dataset_id][0] < flag:
            self._datasets_to_reload[dataset_id] = [flag, time.monotonic()]
        else:
            self._datasets_to_reload[dataset_id][1] = time.monotonic()
        self._flush_datasets(flush)

    def flush(self, force: bool = False):
        """If force is set, all changes are definitely pushed, otherwise the gates are respected"""
        self._flush_datasets(force)

    def _flush_datasets(self, force: bool = False):
        """For datasets"""
        for dataset_id in list(self._datasets_to_reload.keys()):
            if force or (time.monotonic() - self._datasets_to_reload[dataset_id][1]) > self._max_reload_delay:
                self._reload_dataset(dataset_id, self._datasets_to_reload[dataset_id][0])
                del self._datasets_to_reload[dataset_id]

    def _reload_dataset(self, dataset_id, flag):
        """Actually reload a dataset"""
        self.log.info(f"Reload[{flag}] of {dataset_id} proceeding")
        subdir = "flag"
        if flag == ErddapDatasetManager.BAD_FLAG:
            subdir = "badFilesFlag"
        elif flag == ErddapDatasetManager.HARD_FLAG:
            subdir = "hardFlag"
        flag_file = self.bpd / subdir / dataset_id
        if not flag_file.parent.exists():
            flag_file.parent.mkdir()
        with open(flag_file, "w") as h:
            h.write("1")

