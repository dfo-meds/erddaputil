"""Status scraper for ERDDAP"""
import requests
from erddaputil.common import BaseThread
from erddaputil.main.metrics import ScriptMetrics
from autoinject import injector
from erddaputil.erddap.parsing import ErddapStatusParser
import functools
import json
import time


class ErddapStatusScraper(BaseThread):
    """Scrape ERDDAP status page into Prometheus metrics."""

    metrics: ScriptMetrics = None

    @injector.construct
    def __init__(self):
        super().__init__("erddaputil.scraper")
        self.status_scraper_memory_file = self.config.as_path(('erddaputil', 'status_scraper', 'memory_path'), default=None)
        if self.status_scraper_memory_file and not self.status_scraper_memory_file.parent.exists():
            self._log.warning(f"Status scraper memory file directory {self.status_scraper_memory_file} does not exist, checking for default file...")
            self.status_scraper_memory_file = None
        if not self.status_scraper_memory_file:
            self.status_scraper_memory_file = self.config.as_path(("erddaputil", "erddap", "big_parent_directory"), default=None)
            if self.status_scraper_memory_file and self.status_scraper_memory_file.exists():
                self.status_scraper_memory_file = self.status_scraper_memory_file / ".erddaputil_status_scraper_memory"
                self._log.info(f"Using default location for status scraper: {self.status_scraper_memory_file}")
            else:
                self.status_scraper_memory_file = None
        if not self.status_scraper_memory_file:
            self._log.warning(f"Memory file not set for status scraper, metrics may become corrupt when ERDDAPUtil is restarted without restarting ERDDAP as well!")
        self.base_url = self.config.as_str(("erddaputil", "erddap", "base_url"), default=None)
        if self.base_url and self.base_url.endswith("/"):
            self.base_url += "status.html"
        elif self.base_url:
            self.base_url += "/status.html"
        self.enabled = self.config.as_bool(("erddaputil", "status_scraper", "enabled"), default=True)
        self.run_frequency = self.config.as_int(("erddaputil", "status_scraper", "sleep_time_seconds"), default=300)
        # Give ERDDAP a few minutes to get booted up after we boot
        self._startup_at = time.monotonic() + self.config.as_int(("erddaputil", "status_scraper", "start_delay_seconds"), default=180)
        self._last_run = None
        self._remember = {
            'startup_time': '',
            'major_load_time_series_seen': [],
            '_example': 0
        }
        self.set_run_metric(
            self.metrics.summary('erddaputil_status_scraper_runs', labels={'result': 'success'}),
            self.metrics.summary('erddaputil_status_scraper_runs', labels={'result': 'failure'}),
            'observe'
        )
        self._load_remember()

    def _load_remember(self):
        if self.status_scraper_memory_file and self.status_scraper_memory_file.exists():
            with open(self.status_scraper_memory_file, "r") as h:
                self._remember = json.loads(h.read())

    def _save_remember(self):
        if self.status_scraper_memory_file:
            with open(self.status_scraper_memory_file, "w") as h:
                h.write(json.dumps(self._remember))

    def _run(self, *args, **kwargs):
        if not self.enabled:
            return None
        if self._startup_at < time.monotonic():
            return None
        if self._last_run is not None and (time.monotonic() - self._last_run) < self.run_frequency:
            return None
        self._last_run = time.monotonic()
        if not self.base_url:
            return False
        self._log.info(f"Downloading status.html and parsing for statistics")
        try:
            resp = requests.get(self.base_url)
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            self._log.warning(f"ERDDAP was unreachable")
            return False
        except requests.exceptions.HTTPError as ex:
            self._log.warning(f"ERDDAP returned error code {ex.errno}")
            return False
        esp = ErddapStatusParser()
        esp.parse(resp.text)

        mb_to_int = functools.partial(self._remove_units, scale_factor=1024*1024)

        self._log.debug("Checking startup time...")
        # Track the startup time so we can make statistics correct between runs and across boots
        last_startup = esp.info["startup_time"]
        if last_startup != self._remember['startup_time']:
            self._log.notice(f"Resetting metrics since startup_time has changed [from {self._remember['startup_time'] or 'none'} to {last_startup}]")
            self._remember = {
                'startup_time': last_startup,
                'major_load_time_series_seen': []
            }
            self._save_remember()

        self._log.debug("Extracting metrics")
        self._map_gauge_metric(esp, "last_major_load_duration", "erddap_last_major_load_seconds", "Time to load the last major dataset value", transform=self._time_convert)
        self._map_gauge_metric(esp, "griddap_count", "erddap_datasets_grid", "Number of ERDDAP gridded datasets", default=0)
        self._map_gauge_metric(esp, "tabledap_count", "erddap_datasets_table", "Number of ERDDAP tabular datasets", default=0)
        self._map_gauge_metric(esp, "failed_dataset_count", "erddap_datasets_load_failed", "Number of ERDDAP datasets that failed to load", default=0)
        self._map_gauge_metric(esp, "orphan_dataset_count", "erddap_datasets_orphaned", "Number of ERDDAP datasets that are orphaned", default=0)

        self._map_counter_metric(esp, "unique_users", "erddap_users_unique", "Number of unique ERDDAP users", default=0)
        self._map_counter_metric(esp, "task_failed_since_startup", "erddap_task_thread_runs", "Number of times TaskThread runs failed", key=0, labels={"outcome": "failure"})
        self._map_counter_metric(esp, "task_success_since_startup", "erddap_task_thread_runs", "Number of times TaskThread runs succeeded", key=0, labels={"outcome": "success"})
        self._map_counter_metric(esp, "touch_failed_since_startup", "erddap_touch_thread_runs", "Number of times TouchThread runs failed", key=0, labels={"outcome": "failure"})
        self._map_counter_metric(esp, "touch_success_since_startup", "erddap_touch_thread_runs", "Number of times TouchThread runs succeeded", key=0, labels={"outcome": "success"})

        self._map_gauge_metric(esp, "os_info", "erddap_os_cpu_load_ratio", "CPU load [0-1]", key="totalCPULoad")
        self._map_gauge_metric(esp, "os_info", "erddap_os_process_cpu_load_ratio", "Process CPU load [0-1]", key="processCPULoad")
        self._map_gauge_metric(esp, "os_info", "erddap_os_total_memory_bytes", "Total Memory", key="totalMemory", transform=mb_to_int)
        self._map_gauge_metric(esp, "os_info", "erddap_os_free_memory_bytes", "Free Memory", key="freeMemory", transform=mb_to_int)
        self._map_gauge_metric(esp, "os_info", "erddap_os_total_swap_space_bytes", "Total Swap Space", key="totalSwapSpace", transform=mb_to_int)
        self._map_gauge_metric(esp, "os_info", "erddap_os_free_swap_space_bytes", "Free Swap Space", key="freeSwapSpace", transform=mb_to_int)
        self._map_gauge_metric(esp, "active_requests", "erddap_http_requests_active", "Number of current HTTP requests")
        self._map_gauge_metric(esp, "memory_in_use_mb", "erddap_memory_used_bytes", "Memory Used", transform=mb_to_int)
        self._map_gauge_metric(esp, "memory_highwater_mark_mb", "erddap_memory_highwater_bytes", "Memory Highwater", transform=mb_to_int)
        self._map_gauge_metric(esp, "memory_xmax_mb", "erddap_memory_max_bytes", "Memory Max", transform=mb_to_int)

        if esp.has_info('major_load_time_series'):
            self._log.debug(f"Parsing time series")
            for ml_info in esp.info['major_load_time_series']:
                if ml_info[0] in self._remember['major_load_time_series_seen']:
                    continue
                else:
                    self.metrics.counter('erddap_major_loads', description='Total number of major loads').inc(1)
                    self.metrics.summary('erddap_major_load_seconds', description='Total major load time').observe(self._remove_units(ml_info[1]))
                    self.metrics.summary('erddap_major_load_datasets_tried', description='Total number of datasets loaded').observe(int(ml_info[2]))
                    self.metrics.summary('erddap_major_load_datasets_failed', description='Total number of datasets failed').observe(int(ml_info[3]))
                    self.metrics.summary('erddap_major_load_datasets_seen', description='Total number of datasets seen').observe(int(ml_info[4]))
                    self.metrics.counter('erddap_http_requests', description='Number of ERDDAP requests', labels={"outcome": "success"}).inc(int(ml_info[5]))
                    self.metrics.summary('erddap_requests_median_succeeded_seconds', description='Median success time').observe(int(ml_info[6]) / 1000.0)
                    self.metrics.counter('erddap_http_requests', description='Number of ERDDAP requests', labels={"outcome": "failed"}).inc(int(ml_info[7]))
                    self.metrics.summary('erddap_requests_median_failed_seconds', description='Median failure time').observe(int(ml_info[8]) / 1000.0)
                    self.metrics.counter('erddap_http_requests', description='Number of ERDDAP requests', labels={"outcome": "shed"}).inc(int(ml_info[9]))
                    self.metrics.counter('erddap_http_requests', description='Number of ERDDAP requests', labels={"outcome": "memory_fail"}).inc(int(ml_info[10]))
                    self.metrics.counter('erddap_http_requests', description='Number of ERDDAP requests', labels={"outcome": "too_many"}).inc(int(ml_info[11]))
                    self.metrics.counter('erddap_all_threads', description='Number of ERDDAP threads', labels={"state": "waiting"}).inc(int(ml_info[12]))
                    self.metrics.counter('erddap_all_threads', description='Number of ERDDAP threads', labels={"state": "inotify"}).inc(int(ml_info[13]))
                    self.metrics.counter('erddap_all_threads', description='Number of ERDDAP threads', labels={"state": "other"}).inc(int(ml_info[14]))
                    self.metrics.summary('erddap_memory_in_use_bytes', description='Amount of memory in use at the time of a major load').observe(int(ml_info[15]) * 1024 * 1024)
                    self.metrics.counter('erddap_gc_calls', description='Number of garbage collection calls').inc(int(ml_info[16]))
                    self.metrics.summary('erddap_open_files_ratio', description='Number of Open Files').observe(int(ml_info[17][:-1]) / 100.0)
                    self._remember['major_load_time_series_seen'].append(ml_info[0])
                    self._save_remember()

        if esp.has_info('languages_since_startup'):
            self._log.debug(f"Parsing languages list")
            for lang in esp.info['languages_since_startup']:
                metric = self.metrics.counter('erddap_requests_by_language', description='Number of ERDDAP requests by UI language', labels={'language': lang})
                tracker_name = f'erddap_requests_by_language_{lang}'
                val = esp.info['languages_since_startup'][lang]
                if tracker_name in self._remember:
                    metric.inc(val - self._remember[tracker_name])
                else:
                    metric.inc(val)
                self._remember[tracker_name] = val
                self._save_remember()

        self._log.debug("Parsing SgtMap stats")
        self._map_counter_metric(esp, "sgtmap_info", "erddap_sgtmap_topography_tiles_generated", "Number of topographies generated by SgtMap", labels={"cached": "yes"}, key="nFromCache")
        self._map_counter_metric(esp, "sgtmap_info", "erddap_sgtmap_topography_tiles_generated", "Number of topographies generated by SgtMap", labels={"cached": "no"}, key="nNotFromCache")

        self._map_counter_metric(esp, "gshhs_info", "erddap_gshhs_shoreline_tiles_generated", "Number of shorelines generated", labels={"cached": "too_coarse"}, key="nCoarse")
        self._map_counter_metric(esp, "gshhs_info", "erddap_gshhs_shoreline_tiles_generated", "Number of shorelines generated", labels={"cached": "tossed"}, key="nTossed")
        self._map_counter_metric(esp, "gshhs_info", "erddap_gshhs_shoreline_tiles_generated", "Number of shorelines generated", labels={"cached": "yes"}, key="nSuccesses")
        self._map_gauge_metric(esp, "gshhs_info", "erddap_gshhs_shoreline_cache_used", "Number of shorelines stored in cache", key="nCached")
        self._map_gauge_metric(esp, "gshhs_info", "erddap_gshhs_shoreline_cache_size", "Size of the cache", key="nCached_max")

        self._map_counter_metric(esp, 'nat_bound_info', 'erddap_sgtmap_national_boundary_tiles_generated', 'Number of national boundaries generated', labels={"cached": "too_coarse"}, key="nCoarse")
        self._map_counter_metric(esp, 'nat_bound_info', 'erddap_sgtmap_national_boundary_tiles_generated', 'Number of national boundaries generated', labels={"cached": "tossed"}, key="nTossed")
        self._map_counter_metric(esp, 'nat_bound_info', 'erddap_sgtmap_national_boundary_tiles_generated', 'Number of national boundaries generated', labels={"cached": "yes"}, key="nSuccesses")
        self._map_gauge_metric(esp, 'nat_bound_info', 'erddap_sgtmap_national_boundary_cache_used', 'Number of national boundaries stored in the cache', key='nCached')
        self._map_gauge_metric(esp, 'nat_bound_info', 'erddap_sgtmap_national_boundary_cache_size', 'Size of the cache', key='nCached_max')

        self._map_counter_metric(esp, 'state_bound_info', 'erddap_sgtmap_state_boundary_tiles_generated', 'Number of state boundaries generated', labels={"cached": "too_coarse"}, key="nCoarse")
        self._map_counter_metric(esp, 'state_bound_info', 'erddap_sgtmap_state_boundary_tiles_generated', 'Number of state boundaries generated', labels={"cached": "tossed"}, key="nTossed")
        self._map_counter_metric(esp, 'state_bound_info', 'erddap_sgtmap_state_boundary_tiles_generated', 'Number of state boundaries generated', labels={"cached": "yes"}, key="nSuccesses")
        self._map_gauge_metric(esp, 'state_bound_info', 'erddap_sgtmap_state_boundary_cache_used', 'Number of state boundaries stored in the cache', key='nCached')
        self._map_gauge_metric(esp, 'state_bound_info', 'erddap_sgtmap_state_boundary_cache_size', 'Size of the cache', key='nCached_max')

        self._map_counter_metric(esp, 'rivers_info', 'erddap_sgtmap_river_tiles_generated', 'Number of rivers generated', labels={"cached": "too_coarse"}, key="nCoarse")
        self._map_counter_metric(esp, 'rivers_info', 'erddap_sgtmap_river_tiles_generated', 'Number of rivers generated', labels={"cached": "tossed"}, key="nTossed")
        self._map_counter_metric(esp, 'rivers_info', 'erddap_sgtmap_river_tiles_generated', 'Number of rivers generated', labels={"cached": "yes"}, key="nSuccesses")
        self._map_gauge_metric(esp, 'rivers_info', 'erddap_sgtmap_river_cache_used', 'Number of rivers stored in the cache', key='nCached')
        self._map_gauge_metric(esp, 'rivers_info', 'erddap_sgtmap_river_cache_size', 'Size of the cache', key='nCached_max')

        self._log.debug(f"Parsing map sizes for String2")
        if esp.has_info('canon_map_sizes'):
            self.metrics.gauge('erddap_string_interning_canon_map_length', description='Size of String2.canonicalMap').set(len(esp.info['canon_map_sizes']))
            self.metrics.gauge('erddap_string_interning_canon_map_total', description='Total length of all entries in String2.canonicalMap').set(sum(esp.info['canon_map_sizes']))

        if esp.has_info('canon_str_holder_map_sizes'):
            self.metrics.gauge('erddap_string_interning_canon_str_holder_map_length', description='Size of String2.canonicalStringHolderMap').set(len(esp.info['canon_str_holder_map_sizes']))
            self.metrics.gauge('erddap_string_interning_canon_str_holder_map_total', description='Total length of all entries in String2.canonicalStringHolderMap').set(sum(esp.info['canon_str_holder_map_sizes']))

        if esp.has_info('threads'):
            self._log.debug("Parsing thread list")
            by_state = {}
            for t in esp.info['threads']:
                s = esp.info['threads'][t]['state'].lower()
                if s not in by_state:
                    by_state[s] = 0
                by_state[s] += 1
            for state in by_state:
                self.metrics.gauge("erddap_active_threads", description='Number of ERDDAP threads that are not waiting', labels={'state': state}).set(by_state[state])

        self._log.info(f"Metric parsing complete")

    def _time_convert(self, s: str) -> int:
        pieces = s.split(' ')
        total = 0
        for i in range(1, len(pieces), 2):
            if pieces[i] == "seconds" or pieces[i] == "second":
                total += int(pieces[i-1])
            elif pieces[i] == "minutes" or pieces[i] == "minute":
                total += int(pieces[i-1]) * 60
            elif pieces[i] == "hours" or pieces[i] == "hour":
                total += int(pieces[i-1]) * 3600
        return total

    def _remove_units(self, txt, scale_factor=1):
        if isinstance(txt, str):
            while not txt[-1].isdigit():
                txt = txt[:-1]
        return int(txt) * scale_factor

    def _map_counter_metric(self, esp, parsed_name, metric_name, description="", labels=None, default=None, key=None, transform=float):
        val = default
        if esp.has_info(parsed_name):
            val = esp.info[parsed_name]
            if key is not None:
                if isinstance(key, str) and key in val:
                    val = val[key]
                elif isinstance(key, int) and key < len(val):
                    val = val[key]
                else:
                    val = default
        if val is not None and val != "":
            if transform:
                val = transform(val)
            tracker_name = metric_name
            if labels:
                for l in labels:
                    tracker_name += f"::{l}={labels[l]}"
            if tracker_name in self._remember:
                self.metrics.counter(metric_name, description=description, labels=labels).inc(val - float(self._remember[tracker_name]))
            else:
                self.metrics.counter(metric_name, description=description, labels=labels).inc(val)
            self._remember[tracker_name] = val
            self._save_remember()

    def _map_gauge_metric(self, esp, parsed_name, metric_name, description="", labels=None, default=None, key=None, transform=float):
        val = default
        if esp.has_info(parsed_name):
            val = esp.info[parsed_name]
            if key is not None:
                if isinstance(key, str) and key in val:
                    val = val[key]
                elif isinstance(key, int) and key < len(val):
                    val = val[key]
                else:
                    val = default
        if val is not None and val != "":
            if transform:
                val = transform(val)
            self.metrics.gauge(metric_name, description=description, labels=labels).set(val)
