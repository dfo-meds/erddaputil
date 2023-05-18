"""Management of application threads"""
from .main import CommandReceiver
from erddaputil.erddap.logman import ErddapLogManager
from erddaputil.common import BaseApplication
from erddaputil.erddap.datasets import ErddapDatasetManager
from erddaputil.main.metrics import ScriptMetrics
from erddaputil.erddap.status import ErddapStatusScraper
from erddaputil.webapp.common import AuthChecker
from autoinject import injector
import zirconium as zr


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
        self._on_boot()

    def run(self):
        """Kill and recreate threads as necessary"""
        for key in self._defs:
            if key not in self._live or not self._live[key].is_alive():
                self._log.debug(f"(Re)starting thread {key}")
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

    @injector.inject
    def _on_boot(self, cfg: zr.ApplicationConfig = None, edm: ErddapDatasetManager = None, ac: AuthChecker = None):
        if cfg.as_bool(("erddaputil", "fix_erddap_bpd_permissions"), default=True):
            edm.fix_bpd_permissions()
        if cfg.as_bool(("erddaputil", "create_default_user_on_boot"), default=True):
            ac.set_credentials(
                cfg.as_str(("erddaputil", "default_username"), default="admin"),
                cfg.as_str(("erddaputil", "default_password"), default="admin")
            )
        if cfg.as_bool(("erddaputil", "compile_on_boot"), default=True):
            edm.compile_datasets(immediate=True)
