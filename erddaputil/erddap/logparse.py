import hashlib
from erddaputil.common import BaseThread
from graceful_shutdown import ShutdownProtection
import datetime


class ErddapLogParse(BaseThread):

    def __init__(self):
        super().__init__("erddaputil.logparse", 60)
        self._target_dir = self.config.as_path(("erddaputil", "logtail", "output_dir"))

    def _run(self):
        pass