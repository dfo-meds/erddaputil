"""General functions to organize the sending and receiving of AMPQ messages."""
from erddaputil.main.commands import Command, CommandResponse
from autoinject import injector
import zirconium as zr
import functools
import logging
import threading
import signal
import socket
from erddaputil.main.metrics import ScriptMetrics


@injector.injectable_global
class AmpqController:
    """Manages the AMPQ implementations."""

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.handler = None
        self.log = logging.getLogger("erddaputil.ampq")
        mode = self.config.as_str(("erddaputil", "ampq", "implementation"), default="pika")
        try:
            if mode == "pika":
                from ._pika import PikaHandler
                self.handler = PikaHandler(self.config)
            elif mode == "azure_service_bus":
                from ._asb import AzureServiceBusHandler
                self.handler = AzureServiceBusHandler(self.config)
            else:
                self.log.error(f"Invalid AMQP implementation: {mode}")
        except Exception as ex:
            self.log.exception(ex)
        self.is_valid = self.handler.is_config_valid() if self.handler else False

    def send_command(self, cmd: Command, ignore_current_host: bool = True) -> CommandResponse:
        """Sends a command over the AMPQ channel."""
        if not self.is_valid:
            return CommandResponse("No AMQP service configured", "error")
        try:

            # Ignore the current host, since we would have done this locally
            if ignore_current_host:
                cmd.ignore_host(self.handler.hostname)

            # Actually send the message
            self.handler.send_message(cmd.serialize().encode("utf-8"))

            return CommandResponse("AMPQ request queued", "success")

        except Exception as ex:
            self.log.exception(ex)
            return CommandResponse.from_exception(ex)

    @injector.inject
    def receive_until_halted(self, halt_event: threading.Event, csend: "erddaputil.main.main.CommandSender" = None):
        """Run an AMPQ receiving until the given event is set."""
        if not self.is_valid:
            raise ValueError("Invalid AMPQ stack for running")
        self.handler.receive_until_halted(functools.partial(self._handle_message, csend=csend), halt_event)

    def _handle_message(self, message, csend: "erddaputil.main.main.CommandSender"):
        """Handles a message from the AMPQ stack"""
        try:

            # Extract the message
            cmd = Command.unserialize(message)

            # Prevent the command from being rebroadcast
            cmd.allow_broadcast = False

            if self.handler.hostname not in cmd.ignore_on_hosts:
                # Send, but only if we are not ignoring it.
                csend.send_command(cmd)

        except Exception as ex:
            self.log.exception(ex)


class AmpqReceiver:
    """Application that receives and forwards AMPQ messages."""

    manager: AmpqController = None
    metrics: ScriptMetrics = None

    @injector.construct
    def __init__(self):
        self.log = logging.getLogger("erddaputil.ampq")
        self._halt = threading.Event()
        self._break_count = 0

    def sig_handle(self, a, b):
        """Handle signals."""
        self._halt.set()
        self._break_count += 1
        if self._break_count >= 3:
            raise KeyboardInterrupt()

    def run_forever(self):
        """Run the application forever."""
        if not self.manager.is_valid:
            raise ValueError("Configuration is invalid")
        signal.signal(signal.SIGINT, self.sig_handle)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, self.sig_handle)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, self.sig_handle)
        self.manager.receive_until_halted(self._halt)
        self.metrics.halt()


class AmpqHandler:

    def __init__(self, config: zr.ApplicationConfig = None):
        """Initialize the handler."""
        self.credentials = config.as_str(("erddaputil", "ampq", "connection"), default=None)
        self.exchange_name = config.as_str(("erddaputil", "ampq", "exchange_name"), default="erddap_cnc")
        self.hostname = config.as_str(("erddaputil", "ampq", "hostname"), default=None)
        self.cluster_name = config.as_str(("erddaputil", "ampq", "cluster_name"), default="default")
        self.attempt_queue_creation = config.as_bool(("erddaputil", "ampq", "create_queue"), default=True)
        self.topic_name = f"erddap.cluster.{self.cluster_name}"
        self.queue_name = f"erddap_{self.cluster_name}_{self.hostname}"
        self.global_name = "erddap.global"
        if self.hostname is None:
            self.hostname = socket.gethostname()
        self._log = logging.getLogger("erddaputil.ampq")

    def is_config_valid(self) -> bool:
        """Check if the configuration is valid."""
        return self.credentials is not None and self.exchange_name is not None

    def send_message(self, message: bytes) -> bool:
        """Send a message to the AMPQ exchange and return if it was successful."""
        raise NotImplementedError()

    def receive_until_halted(self, content_handler: callable, halt_event: threading.Event):
        """Receive messages and pass them to the handler until the given Event is set."""
        raise NotImplementedError()
