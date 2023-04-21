"""Support for handling commands on a local port and returning a response"""
import socket
from autoinject import injector
import zirconium as zr
from select import select
from erddaputil.common import BaseThread
import itsdangerous
import time

DEFAULT_PORT = 7012
DEFAULT_HOST = "127.0.0.1"


@injector.injectable_global
class Serializer:
    """Handles serialization in a consistent fashion"""

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.serializer = itsdangerous.URLSafeSerializer(
            self.config.as_str(("erddaputil", "secret_key")),
            "command_message_serializer"
        )

    def serialize(self, content):
        return self.serializer.dumps(content)

    def unserialize(self, data):
        return self.serializer.loads(data)


class Command:
    """Represents a command being executed by the daemon."""

    def __init__(self, name, *args, **kwargs):
        self.name = name
        self.args = args or []
        self.kwargs = kwargs or {}

    @injector.inject
    def serialize(self, _serializer: Serializer = None) -> str:
        return _serializer.serialize({
            "name": self.name,
            "args": self.args,
            "kwargs": self.kwargs
        })

    @staticmethod
    @injector.inject
    def unserialize(message: str, _serializer: Serializer = None):
        message = _serializer.unserialize(message)
        return Command(message['name'], *message['args'], **message['kwargs'])


class CommandResponse:
    """Represents a response by the command. """

    def __init__(self, message, state='success'):
        self.message = message
        self.state = state

    @injector.inject
    def serialize(self, _serializer: Serializer = None) -> str:
        return _serializer.serialize({
            "message": self.message,
            "state": self.state,
        })

    @staticmethod
    def from_exception(ex: Exception):
        return CommandResponse(f"{type(ex)}: {str(ex)}", "error")

    @staticmethod
    @injector.inject
    def unserialize(message: str, _serializer: Serializer = None):
        message = _serializer.unserialize(message)
        return CommandResponse(message['message'], message['state'])


class SocketTimeout(Exception):
    pass


def recv_with_end(clientsocket, buffer_size: int = 1024, timeout: float = 5):
    """Receive bytes until the end transmission flag is seen."""
    data = bytearray()
    _start = time.monotonic()
    while not (data and data[-1] == 4):
        if time.monotonic() - _start > timeout:
            raise SocketTimeout()
        try:
            data.extend(_recv_with_timeout(clientsocket, buffer_size, 0.25))
        except SocketTimeout:
            pass
    return data[:-1]


def _recv_with_timeout(sock, buffer_size: int = 1024, timeout: float = 0.25):
    sock.setblocking(0)
    ready = select([sock], [], [], timeout)
    if ready[0]:
        return sock.recv(buffer_size)
    raise SocketTimeout


def send_with_end(clientsocket, content, end_flag=b"\4"):
    """Send bytes and append the end transmission flag."""
    clientsocket.sendall(content + end_flag)


@injector.injectable_global
class CommandRegistry:
    """Used to register commands using a Flask routing like pattern before the configuration is instantiated."""

    def __init__(self):
        self._routing = {}
        self._setup = []
        self._shutdown = []
        self._tidy = []

    def on_setup(self, cb):
        self._setup.append(cb)

    def on_shutdown(self, cb):
        self._shutdown.append(cb)

    def on_tidy(self, cb):
        self._tidy.append(cb)

    def add_route(self, name, cb):
        self._routing[name] = cb

    def route_command(self, cmd: Command) -> CommandResponse:
        if cmd.name in self._routing:
            return self._routing[cmd.name](*cmd.args, **cmd.kwargs)
        raise ValueError(f"Command not recognized {cmd.name}")

    def setup(self):
        for cb in self._setup:
            cb()

    def shutdown(self):
        for cb in self._shutdown:
            cb()

    def tidy(self):
        for cb in self._tidy:
            cb()


@injector.injectable_global
class CommandAndControl:
    """Command and control class to send/route commands."""

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self._host = self.config.as_str(("erddaputil", "service", "host"), default=DEFAULT_HOST)
        self._port = self.config.as_int(("erddaputil", "service", "port"), default=DEFAULT_PORT)

    def send_command(self, cmd: Command) -> CommandResponse:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((self._host, self._port))
            send_with_end(sock, cmd.serialize().encode("utf-8"))
            return CommandResponse.unserialize(recv_with_end(sock).decode("utf-8"))


class CommandReceiver(BaseThread):
    """Thread instance to handle incoming requests."""

    reg: CommandRegistry = None

    @injector.construct
    def __init__(self):
        super().__init__("erddaputil.receiver", 0)
        self._host = self.config.as_str(("erddaputil", "service", "host"), default=DEFAULT_HOST)
        self._port = self.config.as_int(("erddaputil", "service", "port"), default=DEFAULT_PORT)
        self._server = None
        self._backlog = self.config.as_int(("erddaputil", "service", "backlog"), default=20)
        self._listen_block = self.config.as_float(("erddaputil", "service", "listen_block_seconds"), default=0.25)

    def _setup(self):
        self.reg.setup()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.bind((self._host, self._port))
        self._server.listen(self._backlog)

    def _run(self):
        ready, _, _ = select([self._server], [], [], self._listen_block)
        if ready:
            clientsocket, address = self._server.accept()
            try:
                send_with_end(clientsocket, self.handle(address, recv_with_end(clientsocket)))
            except SocketTimeout:
                self._log.error("Client connection timed out")
            clientsocket.close()
        self.reg.tidy()

    def handle(self, address, raw_data: bytes) -> bytes:
        response = None
        try:
            cmd = Command.unserialize(raw_data.decode("utf-8", errors="replace"))
            response = self.reg.route_command(cmd)
            if response is None or response is True:
                response = CommandResponse("success")
            elif response is False:
                response = CommandResponse("failure", "error")
            elif not isinstance(response, CommandResponse):
                response = CommandResponse(str(response))
        except Exception as ex:
            response = CommandResponse.from_exception(ex)
        return response.serialize().encode("utf-8", errors="replace")

    def _cleanup(self):
        if self._server:
            self._server.close()
        self.reg.shutdown()


class CommandGroup:

    cr: CommandRegistry = None

    @injector.construct
    def __init__(self):
        self._cnc = None

    @injector.inject
    def remote_command(self, name, *args, cnc: CommandAndControl = None, **kwargs):
        cnc.send_command(Command(name, *args, **kwargs))

    def on_setup(self, fn):
        self.cr.on_setup(fn)
        return fn

    def on_shutdown(self, fn):
        self.cr.on_shutdown(fn)
        return fn

    def on_tidy(self, fn):
        self.cr.on_tidy(fn)
        return fn

    def on_call(self, name, fn):
        self.cr.add_route(name, fn)
        return fn

    def route(self, name):
        """Decorator to add a command route."""
        def decorator(fn):
            self.cr.add_route(name, fn)
            return fn
        return decorator
