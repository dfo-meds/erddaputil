"""Support for handling commands on a local port and returning a response"""
import socket
from autoinject import injector
import zirconium as zr
from select import select
from erddaputil.common import BaseThread
from erddaputil.main.commands import Command, CommandResponse, CommandRegistry
import time

DEFAULT_PORT = 9172
DEFAULT_HOST = "127.0.0.1"


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
class CommandSender:
    """Command and control class to send/route commands."""

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self._host = self.config.as_str(("erddaputil", "daemon", "host"), default=DEFAULT_HOST)
        self._port = self.config.as_int(("erddaputil", "daemon", "port"), default=DEFAULT_PORT)

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
            self._log.exception(ex)
            response = CommandResponse.from_exception(ex)
        return response.serialize().encode("utf-8", errors="replace")

    def _cleanup(self):
        if self._server:
            self._server.close()
            self._server = None
        self.reg.shutdown()

