from autoinject import injector
import zirconium as zr
import itsdangerous


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

    def __init__(self, name, *args, _broadcast: bool = True, **kwargs):
        self.name = name
        self.args = args or []
        self.kwargs = kwargs or {}
        self.allow_broadcast = _broadcast
        self.ignore_on_hosts = []

    def ignore_host(self, hostname):
        self.ignore_on_hosts.append(str(hostname))

    @injector.inject
    def serialize(self, _serializer: Serializer = None) -> str:
        return _serializer.serialize({
            "name": self.name,
            "args": self.args,
            "kwargs": self.kwargs,
            "ignore": self.ignore_on_hosts
        })

    @staticmethod
    @injector.inject
    def unserialize(message: str, _serializer: Serializer = None):
        message = _serializer.unserialize(message)
        cmd = Command(message['name'], *message['args'], **message['kwargs'])
        if "ignore" in message and message["ignore"]:
            cmd.ignore_on_hosts.extend(message["ignore"])
        return cmd


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


@injector.injectable_global
class CommandAndControl:

    config: zr.ApplicationConfig = None
    local_sender: "erddaputil.main.manager.CommandSender" = None
    ampq_sender: "erddaputil.ampq.ampq.AmpqManager" = None

    @injector.construct
    def __init__(self):
        self._send_to_local = self.config.as_bool(("erddaputil", "use_local_daemon"), default=True)
        self._send_to_ampq = self.config.as_bool(("erddaputil", "use_ampq_exchange"), default=False)

    def send_command(self, cmd: Command) -> CommandResponse:
        response = None
        if self._send_to_ampq and cmd.allow_broadcast and self.ampq_sender.is_valid:
            response = self.ampq_sender.send_command(cmd)
        if self._send_to_local:
            response = self.local_sender.send_command(cmd)
        return response


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

    @injector.inject
    def send_command(self, cmd: Command, cnc: CommandAndControl = None) -> CommandResponse:
        return cnc.send_command(cmd)

    def setup(self):
        for cb in self._setup:
            cb()

    def shutdown(self):
        for cb in self._shutdown:
            cb()

    def tidy(self):
        for cb in self._tidy:
            cb()


class CommandGroup:

    cr: CommandRegistry = None

    @injector.construct
    def __init__(self):
        self._cnc = None

    def remote_command(self, name, *args, **kwargs) -> CommandResponse:
        return self.cr.send_command(Command(name, *args, **kwargs))

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
