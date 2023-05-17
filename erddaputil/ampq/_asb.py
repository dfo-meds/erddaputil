"""AzureServiceBus integration"""
import threading
from .ampq import AmpqHandler
import azure.servicebus as sb
import azure.servicebus.management as sbm
import azure.servicebus.exceptions as sbe
from azure.core.exceptions import ResourceExistsError


class AzureServiceBusHandler(AmpqHandler):
    """Implement AMPQ handling for AzureServiceBus."""

    def send_message(self, message: bytes) -> bool:
        """Send a message to the AMPQ exchange and return if it was successful."""
        try:
            client = sb.ServiceBusClient.from_connection_string(self.credentials)
            with client:
                sender = client.get_topic_sender(self.exchange_name)
                with sender:
                    message = sb.ServiceBusMessage(message, subject=self.topic_name)
                    sender.send_messages(message)
                    return True
        except sbe.ServiceBusError as ex:
            self._log.exception("Error sending message to AzureServiceBus")
            return False

    def receive_until_halted(self, content_handler: callable, halt_event: threading.Event):
        """Receive messages and pass them to the handler until the given Event is set."""
        if self.attempt_queue_creation:
            self._log.debug("Attempting to create ServiceBus subscription and rules")
            self._create_subscription()
        with sb.ServiceBusClient.from_connection_string(self.credentials) as client:
            with client.get_subscription_receiver(self.exchange_name, self.queue_name) as receiver:
                while not halt_event.is_set():
                    messages = receiver.receive_messages(1, 1)
                    for message in messages:
                        content_handler(message.body)
                        receiver.complete_message(message)

    def _create_subscription(self):
        with sbm.ServiceBusAdministrationClient.from_connection_string(self.credentials) as mc:
            try:
                mc.create_subscription(self.exchange_name, self.queue_name)
            except ResourceExistsError:
                pass
            try:
                mc.create_rule(
                    self.exchange_name,
                    self.queue_name,
                    "IncludeClusterMessages",
                    filter=sbm.CorrelationRuleFilter(label=self.topic_name)
                )
            except ResourceExistsError:
                pass
            try:
                mc.create_rule(
                    self.exchange_name,
                    self.queue_name,
                    "IncludeGlobalMessages",
                    filter=sbm.CorrelationRuleFilter(label=self.global_name)
                )
            except ResourceExistsError:
                pass
