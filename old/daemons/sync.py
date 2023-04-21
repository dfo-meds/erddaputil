import json
import time

from old.daemons.metrics import ScriptMetrics
import queue
from autoinject import injector
import zirconium as zr
import threading


class ErddapSyncManager(threading.Thread):

    config: zr.ApplicationConfig = None
    metrics: ScriptMetrics = None

    @injector.construct
    def __init__(self, work_queue: queue.Queue):
        super().__init__()
        self.erddap_directory = None
        self.erddap_directory = self.config.as_path(("erddaputil", "big_parent_dir"))
        if self.erddap_directory is None or not self.erddap_directory.exists():
            self.erddap_directory = None
            raise ValueError(f"ERDDAP's big parent directory not found: {self.erddap_directory}")
        self._data_file_count = self.metrics.counter(f"erddaputil_sync_data_files_received")
        self._config_file_count = self.metrics.counter(f"erddaputil_sync_config_files_received")
        self._metadata_file_count = self.metrics.counter(f"erddaputil_sync_metadata_files_received")
        self._work_queue = work_queue
        self._halt = threading.Event()
        self._wait_time = 0.25
        self.daemon = True
        self._reload_datasets = set()
        self._datasets_xml_reload = False
        self._metadata_reload = False
        from old.util.datasets import ErddapDatasetManager
        self.dsm = ErddapDatasetManager()
        self._max_queued_datasets = self.config.as_int(("erddaputil", "sync", "max_deferred_datasets"), default=1)
        self._dataset_reload_max_delay = self.config.as_int(("erddaputil", "sync", "max_dataset_reload_delay_seconds"), default=300)
        self._config_reload_max_delay = self.config.as_int(("erddaputil", "sync", "max_config_reload_delay_seconds"), default=300)
        self._dataset_reload_delayed_since = None
        self._config_reload_delayed_since = None

    def halt(self):
        self._halt.set()

    def _flush_all(self):
        self._flush_reloads()
        self._flush_datasets()

    def _flush_check(self):
        n = time.monotonic()
        if (self._config_reload_delayed_since is not None) and (n - self._config_reload_delayed_since) >= self._config_reload_max_delay:
            self._flush_reloads()
        if (self._dataset_reload_delayed_since is not None) and (n - self._dataset_reload_delayed_since) >= self._dataset_reload_max_delay:
            self._flush_datasets()

    def _reload_dataset(self, dataset_id):
        if len(self._reload_datasets) == self._max_queued_datasets and dataset_id not in self._reload_datasets:
            self._flush_datasets()
        self._data_file_count.increment()
        self._reload_datasets.add(dataset_id)
        if self._dataset_reload_delayed_since is None:
            self._dataset_reload_delayed_since = time.monotonic()

    def _reload_metadata(self):
        self._metadata_file_count.increment()
        self._metadata_reload = True
        if self._config_reload_delayed_since is None:
            self._config_reload_delayed_since = time.monotonic()

    def _reload_config(self):
        self._config_file_count.increment()
        self._datasets_xml_reload = True
        if self._config_reload_delayed_since is None:
            self._config_reload_delayed_since = time.monotonic()

    def _flush_datasets(self):
        for dataset in self._reload_datasets:
            self.dsm.reload_dataset(dataset, 1)
        self._reload_datasets = set()

    def _flush_reloads(self):
        if self._datasets_xml_reload:
            self.dsm.compile_datasets(reload_all_datasets=self._metadata_reload)
            if self._metadata_reload:
                self._reload_datasets = set()
            self._datasets_xml_reload = False
            self._metadata_reload = False
        elif self._metadata_reload:
            self.dsm.reload_all_datasets()
            self._metadata_reload = False
            self._reload_datasets = set()

    @injector.as_thread_run
    def run(self):
        while not self._halt.is_set():
            try:
                item = self._work_queue.get_nowait()
                metadata = json.loads(item['metadata']) if item['metadata'] else {}
                if 'erddap_type' not in metadata:
                    pass
                elif metadata['erddap_type'] == "data" and 'dataset_id' in metadata:
                    self._reload_dataset(metadata['dataset_id'])
                elif metadata['erddap_type'] == "metadata":
                    self._reload_metadata()
                elif metadata['erddap_type'] == 'config':
                    self._reload_config()
                self._flush_check()
            except queue.Empty:
                self._flush_check()
                self._halt.wait(self._wait_time)
        self._flush_all()
