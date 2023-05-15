"""Management of application threads"""
import threading
from .main import CommandReceiver
import logging
import signal
from erddaputil.erddap.logman import ErddapLogManager
from erddaputil.common import init_config
from erddaputil.erddap.datasets import ErddapDatasetManager
from erddaputil.main.metrics import ScriptMetrics
from erddaputil.erddap.status import ErddapStatusScraper
from autoinject import injector


class Application:
    """Manages all the daemon threads"""

    def __init__(self):
        init_config()
        self._live = {}
        # These are the classes we create and run, they should extend BaseThread
        self._defs = {
            "receiver": CommandReceiver,
            "logman": ErddapLogManager,
            "status_scarper": ErddapStatusScraper
        }
        self._halt = threading.Event()
        self._break_count = 0
        self._sleep = 0.5
        self.log = logging.getLogger("erddaputil")
        self._command_groups = []

    def _register_signal_handler(self, signame):
        """Register a signal handler"""
        if hasattr(signal, signame):
            self.log.debug(f"Registering {signame}")
            signal.signal(getattr(signal, signame), self.sig_handle)

    def sig_handle(self, a, b):
        """Handle signals"""
        self.log.info("Termination signal received")
        self._halt.set()
        self._break_count += 1
        if self._break_count >= 3:
            self.log.warning("Terminating abruptly")
            raise KeyboardInterrupt()

    @injector.inject
    def _setup(self, edm: ErddapDatasetManager = None):
        """Pre-run setup stuff"""
        # Make sure command groups got loaded here and give ErddapDatasetManager a chance to fail
        from erddaputil.erddap.commands import cg as _erddap_cg
        self._command_groups.append(_erddap_cg)
        self.log.info("Adding signal handlers")
        self._register_signal_handler("SIGINT")
        self._register_signal_handler("SIGTERM")
        self._register_signal_handler("SIGBREAK")
        self._register_signal_handler("SIGQUIT")

    def run_forever(self):
        """Run the application until interrupted"""
        self.log.info("Checking configuration...")
        self._setup()
        try:
            self.log.info("Starting...")
            while not self._halt.is_set():
                self._reap_and_sow()
                self._halt.wait(self._sleep)
        finally:
            self.log.info("Cleaning up")
            self._cleanup()
            self.log.info("Exiting")

    def _reap_and_sow(self):
        """Kill and recreate threads as necessary"""
        for key in self._defs:
            if key not in self._live or not self._live[key].is_alive():
                self.log.info(f"Starting thread {key}")
                self._live[key] = self._defs[key]()
                self._live[key].start()

    @injector.inject
    def _cleanup(self, metrics: ScriptMetrics = None):
        """Wrap it up"""
        self.log.info("Cleaning up")
        # Tell everything to stop after the next run
        for key in self._live:
            self._live[key].terminate()
        # Join all of the threads
        for key in self._live:
            self._live[key].join()
        # Last, we will halt metrics to make sure everything got sent.
        metrics.halt()
