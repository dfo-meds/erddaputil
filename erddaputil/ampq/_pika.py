"""Pika integration"""
import pika
from pika.exceptions import UnroutableError
import threading
from .ampq import AmpqHandler


class PikaHandler(AmpqHandler):
    """Handles sending and receiving using the pika library."""

    def send_message(self, message: bytes) -> bool:
        """Send a message to the AMPQ exchange and return if it was successful."""
        conn = pika.BlockingConnection(parameters=pika.URLParameters(self.credentials))
        channel = conn.channel()
        channel.confirm_delivery()
        try:
            channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=self.topic_name,
                body=message,
                properties=pika.BasicProperties(
                    content_type="text/plain",
                    delivery_mode=pika.DeliveryMode.Transient
                )
            )
            return True
        except UnroutableError:
            self._log.exception("Error sending message via pika")
            return False

    def receive_until_halted(self, content_handler: callable, halt_event: threading.Event):
        """Receive messages and pass them to the handler until the given Event is set."""
        self._log.debug("Opening AMPQ connection")
        conn = pika.BlockingConnection(parameters=pika.URLParameters(self.credentials))
        channel = conn.channel()
        if self.attempt_queue_creation:
            self._log.debug("Creating and binding AMPQ queue")
            channel.queue_declare(self.queue_name, durable=True)
            channel.queue_bind(self.queue_name, self.exchange_name, routing_key=self.global_name)
            channel.queue_bind(self.queue_name, self.exchange_name, routing_key=self.topic_name)
        for mf, hf, body in channel.consume(self.queue_name, auto_ack=False, inactivity_timeout=1):
            if body is not None:
                content_handler(body)
                channel.basic_ack(mf.delivery_tag)
            if halt_event.is_set():
                self._log.debug("Closing AMPQ channel")
                channel.cancel()
                break
