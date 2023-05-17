"""Management of application threads"""
import threading
from .main import CommandReceiver
import logging
import signal
from erddaputil.erddap.logman import ErddapLogManager
from erddaputil.common import BaseApplication
from erddaputil.erddap.datasets import ErddapDatasetManager
from erddaputil.main.metrics import ScriptMetrics
from erddaputil.erddap.status import ErddapStatusScraper
from autoinject import injector


class Application(BaseApplication):
    """Manages all the daemon threads"""

    def __init__(self):
        super().__init__("erddaputil.daemon")
        self._live = {}
        # These are the classes we create and run, they should extend BaseThread
        self._defs = {
            "receiver": CommandReceiver,
            "logman": ErddapLogManager,
            "status_scarper": ErddapStatusScraper
        }
        self._command_groups = []

    @injector.inject
    def _startup(self, edm: ErddapDatasetManager = None):
        """Pe-run setup stuff"""
        # Make sure command groups got loaded here and give ErddapDatasetManager a chance to fail
        from erddaputil.erddap.commands import cg as _erddap_cg
        self._command_groups.append(_erddap_cg)

    def run(self):
        """Kill and recreate threads as necessary"""
        for key in self._defs:
            if key not in self._live or not self._live[key].is_alive():
                self._log.debug(f"Starting thread {key}")
                self._live[key] = self._defs[key]()
                self._live[key].start()

    @injector.inject
    def _shutdown(self, metrics: ScriptMetrics = None):
        """Wrap it up"""
        # Tell everything to stop after the next run
        for key in self._live:
            self._live[key].terminate()
        # Join all of the threads
        for key in self._live:
            self._live[key].join()
        # Last, we will halt metrics to make sure everything got sent.
        metrics.halt()
