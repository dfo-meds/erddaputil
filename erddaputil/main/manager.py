"""Management of application threads"""
import threading
from .main import CommandReceiver
import logging
import signal
from erddaputil.erddap.logs import ErddapLogManager
from erddaputil.common import init_config
from erddaputil.erddap.datasets import ErddapDatasetManager
from erddaputil.main.metrics import ScriptMetrics
from erddaputil.erddap.logtail import ErddapLogTail
from autoinject import injector


class Application:

    def __init__(self):
        init_config()
        self._live = {}
        self._defs = {
            "receiver": CommandReceiver,
            "logman": ErddapLogManager,
            # TODO: Need to complete the log tail reader
            # "logtail": ErddapLogTail
        }
        self._halt = threading.Event()
        self._break_count = 0
        self._sleep = 0.5
        self.log = logging.getLogger("erddaputil")
        self._command_groups = []

    def _register_signal_handler(self, signame):
        if hasattr(signal, signame):
            self.log.debug(f"Registering {signame}")
            signal.signal(getattr(signal, signame), self.sig_handle)

    @injector.inject
    def _setup(self, edm: ErddapDatasetManager = None):
        # Make sure command groups got loaded here
        from erddaputil.erddap.commands import cg as _erddap_cg
        self._command_groups.append(_erddap_cg)
        self.log.info("Adding signal handlers")
        self._register_signal_handler("SIGINT")
        self._register_signal_handler("SIGTERM")
        self._register_signal_handler("SIGBREAK")
        self._register_signal_handler("SIGQUIT")


    def sig_handle(self, a, b):
        """Handle SIGINT, SIGTERM, SIGBREAK"""
        self.log.info("Termination signal received")
        self._halt.set()
        self._break_count += 1
        if self._break_count >= 3:
            self.log.warning("Terminating abruptly")
            raise KeyboardInterrupt()

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
            self._cleanup()
            self.log.info("Exiting")

    def _reap_and_sow(self):
        for key in self._defs:
            if key not in self._live or not self._live[key].is_alive():
                self.log.info(f"Starting thread {key}")
                self._live[key] = self._defs[key]()
                self._live[key].start()

    @injector.inject
    def _cleanup(self, metrics: ScriptMetrics = None):
        self.log.info("Cleaning up")
        for key in self._live:
            self._live[key].terminate()
        for key in self._live:
            self._live[key].join()
        # Last, we will halt metrics to make sure everything got sent.
        metrics.halt()
