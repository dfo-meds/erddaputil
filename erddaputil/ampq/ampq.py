from erddaputil.main.commands import Command, CommandResponse
from autoinject import injector
import zirconium as zr
import functools


class AmpqSender:

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.handler = None
        self.cluster_name = self.config.as_str(("erddaputil", "ampq", "cluster_name"), default="default")
        self.topic_name = f"erddap.cluster.{self.cluster_name}"
        mode = self.config.as_str(("erddaputil", "ampq", "implementation"), default="pika")
        try:
            if mode == "pika":
                self.handler = _PikaHandler(self.config)
            elif mode == "azure_service_bus":
                self.handler = _AzureServiceBusHandler(self.config)
        except Exception as ex:
            pass
        if self.handler is None:
            self.is_valid = False
        else:
            self.is_valid = self.handler.is_valid()

    def send_command(self, cmd: Command) -> CommandResponse:
        if not self.is_valid:
            return CommandResponse("No AMQP service configured", "error")
        try:
            self.handler.send_message(self.topic_name, cmd.serialize())
            return CommandResponse("AMPQ request queued", "success")
        except Exception as ex:
            return CommandResponse(f"{type(ex)}: {str(ex)}", "error")

    @injector.inject
    def run_forever(self, halt_event, creg: "erddaputil.main.commands.CommandRegistry" = None):
        if not self.is_valid:
            raise ValueError("Invalid AMPQ stack for running")
        self.handler.receive_forever(functools.partial(self.handle_message, creg=creg), halt_event)

    def handle_message(self, message, creg: "erddaputil.main.commands.CommandRegistry"):
        try:
            cmd = Command.unserialize(message)
            creg.route_command(cmd)
        except Exception as ex:
            pass


class _PikaHandler:

    def __init__(self, config: zr.ApplicationConfig = None):
        self.credentials = config.as_str(("erddaputil", "ampq", "connection"), default=None)
        self.exchange_name = config.as_str(("erddaputil", "ampq", "exchange_name"), default="erddap_cnc")
        self.queue_name = f"erddap_{self.cluster_name}_{self.hostname}"
        self.hostname = config.as_str(("erddaputil", "ampq", "hostname"), default=None)
        self.cluster_name = config.as_str(("erddaputil", "ampq", "cluster_name"), default="default")

    def send_message(self, topic, message):
        import pika
        from pika.exceptions import UnroutableError
        conn = pika.BlockingConnection(parameters=pika.URLParameters(self.credentials))
        channel = conn.channel()
        channel.confirm_delivery()
        try:
            channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=topic,
                body=message,
                properties=pika.BasicProperties(
                    content_type="text/plain",
                    delivery_mode=pika.DeliveryMode.Transient
                )
            )
            return True
        except UnroutableError:
            return False

    def is_valid(self):
        return self.credentials is not None and self.exchange_name is not None

    def receive_forever(self, message_content_handler, halt_event):
        import pika
        conn = pika.BlockingConnection(parameters=pika.URLParameters(self.credentials))
        channel = conn.channel()
        channel.queue_declare(self.queue_name, durable=True)
        for mf, hf, body in channel.consume(self.queue_name, auto_ack=False, inactivity_timeout=1):
            if body is not None:
                message_content_handler(body)
                channel.basic_ack(mf.delivery_tag)
            if halt_event.is_set():
                channel.cancel()
                break


class _AzureServiceBusHandler:

    def __init__(self, config: zr.ApplicationConfig = None):
        self.connect_str = config.as_str(("erddaputil", "ampq", "connection"), default=None)
        self.exchange_name = config.as_str(("erddaputil", "ampq", "exchange_name"), default="erddap_cnc")
        self.hostname = config.as_str(("erddaputil", "ampq", "hostname"), default=None)
        self.cluster_name = config.as_str(("erddaputil", "ampq", "cluster_name"), default="default")
        self.sub_name = f"erddap_{self.cluster_name}_{self.hostname}"

    def send_message(self, topic, message):
        import azure.servicebus as sb
        client = sb.ServiceBusClient.from_connection_string(self.connect_str)
        with client:
            sender = client.get_topic_sender(self.exchange_name)
            with sender:
                message = sb.ServiceBusMessage(message, subject=topic)
                sender.send_messages(message)

    def is_valid(self):
        return self.connect_str is not None

    def receive_forever(self, message_content_handler, halt_event):
        import azure.servicebus as sb
        with sb.ServiceBusClient.from_connection_string(self.connect_str) as client:
            with client.get_subscription_receiver(self.exchange_name, self.sub_name) as receiver:
                while not halt_event.is_set():
                    messages = receiver.receive_messages(1, 1)
                    for message in messages:
                        message_content_handler(message.body)
                        receiver.complete_message(message)

    def _create_subscription(self):
        import azure.servicebus.management as sbm
        from azure.core.exceptions import ResourceExistsError
        with sbm.ServiceBusAdministrationClient.from_connection_string(self.connect_str) as mc:
            try:
                mc.create_subscription(self.exchange_name, self.sub_name)
            except ResourceExistsError:
                pass
            try:
                mc.create_rule(
                    self.exchange_name,
                    self.sub_name,
                    "IncludeClusterMessages",
                    filter=sbm.CorrelationRuleFilter(label=f"erddap.cluster.{self.cluster_name}")
                )
            except ResourceExistsError:
                pass
            try:
                mc.create_rule(
                    self.exchange_name,
                    self.sub_name,
                    "IncludeGlobalMessages",
                    filter=sbm.CorrelationRuleFilter(label="erddap.global")
                )
            except ResourceExistsError:
                pass
