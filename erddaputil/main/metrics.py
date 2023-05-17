from autoinject import injector
import threading
import queue
import zirconium as zr
import base64
import aiohttp
import asyncio
import zrlog
from erddaputil.common import load_object, BaseThread


class _Metric:

    def __init__(self, metric_type, metric_name, labels, description, method, kwargs):
        self.metric_type = metric_type
        self.metric_name = metric_name
        self.labels = labels or {}
        self.description = description or ""
        self.method = method
        self.arguments = kwargs or {}

    def to_dict(self):
        return {
            "metric_type": self.metric_type,
            "metric_name": self.metric_name,
            "labels": self.labels,
            "description": self.description,
            "method": self.method,
            "arguments": self.arguments
        }


class AbstractMetric:

    def __init__(self, metric_type, metric_parent, name, labels=None, description=""):
        self.metric_type = metric_type
        self.parent = metric_parent
        self.name = name
        self.labels = labels
        self.description = description

    def send_message(self, method, **kwargs):
        self.parent.send_message(_Metric(self.metric_type, self.name, self.labels, self.description, method, kwargs))


class _ScriptCounterMetric(AbstractMetric):

    def __init__(self, *args, **kwargs):
        super().__init__('counter', *args, **kwargs)

    def inc(self, amount=1, exemplar=None):
        self.send_message('inc', amount=amount, exemplar=exemplar)


class _ScriptGaugeMetric(AbstractMetric):

    def __init__(self, *args, **kwargs):
        super().__init__('gauge', *args, **kwargs)

    def inc(self, amount=1):
        self.send_message('inc', amount=amount)

    def dec(self, amount=1):
        self.send_message('dec', amount=amount)

    def set(self, amount):
        self.send_message('set', amount=amount)


class _ScriptSummaryMetric(AbstractMetric):

    def __init__(self, *args, **kwargs):
        super().__init__('summary', *args, **kwargs)

    def observe(self, value):
        self.send_message('observe', value=value)


class _ScriptHistogramMetric(AbstractMetric):

    def __init__(self, *args, buckets=None, **kwargs):
        super().__init__('histogram', *args, **kwargs)
        self.buckets = buckets

    def observe(self, value, exemplar=None):
        self.send_message('observe', value=value, exemplar=exemplar, _buckets=self.buckets)


class _ScriptInfoMetric(AbstractMetric):

    def __init__(self, *args, **kwargs):
        super().__init__('info', *args, **kwargs)

    def info(self, key, value):
        self.send_message('info', key=key, value=value)


class _ScriptEnumMetric(AbstractMetric):

    def __init__(self, *args, **kwargs):
        super().__init__('enum', *args, **kwargs)

    def state(self, state_name):
        self.send_message('state', state_name=state_name)


class LocalPrometheusSendThread(BaseThread):

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        super().__init__("erddaputil.main.metrics.localprom")
        self.messages = queue.SimpleQueue()

        host = self.config.as_str(("erddaputil", "localprom", "host"), default="localhost")
        port = self.config.as_int(("erddaputil", "localprom", "port"), default=5000)
        self._endpoint = self.config.as_str(("erddaputil", "localprom", "metrics_path"), default=f"http://{host}:{port}/push")
        self._log.debug(f"Local prometheus send thread configured to send to {self._endpoint}")

        username = self.config.as_str(("erddaputil", "localprom", "username"))
        password = self.config.as_str(("erddaputil", "localprom", "password"))
        unpw = f"{username}:{password}"
        self._headers = {
            "Authorization": f"basic {base64.b64encode(unpw.encode('utf-8')).decode('ascii')}"
        }
        self._max_concurrent_tasks = self.config.as_int(("erddaputil", "localprom", "max_tasks"), default=10)
        self._max_messages_to_send = self.config.as_int(("erddaputil", "localprom", "batch_size"), default=200)
        self._message_wait_time = self.config.as_float(("erddaputil", "localprom", "batch_wait_seconds"), default=2)
        self._max_retries = self.config.as_int(("erddaputil", "localprom", "max_retries"), default=3)
        self._retry_delay = self.config.as_float(("erddaputil", "localprom", "retry_delay_seconds"), default=1)
        self._active_tasks = []

    def send_message(self, metric: _Metric) -> bool:
        if self._halt.is_set():
            return False
        self.messages.put_nowait(metric)
        return True

    @injector.as_thread_run
    def run(self):
        return asyncio.run(self._async_entry_point())

    async def _async_entry_point(self):
        async with aiohttp.ClientSession() as session:
            while not self._halt.is_set():
                # If we have room for more tasks and there are messages, queue them up until no more are here
                while len(self._active_tasks) < self._max_concurrent_tasks and not self.messages.empty():
                    await self._batch_send(session)
                # If there are tasks pending, give them a chance to run
                if self._active_tasks:
                    await self._process_tasks(True)
                # Otherwise, just sleep for a bit
                else:
                    await asyncio.sleep(self._loop_delay)
            # Halt has been set, queue up the rest of the messages
            self._log.info(f"Processing final messages...")
            while not self.messages.empty():
                if not await self._batch_send(session):
                    break
            # Wait for the tasks to be completed
            self._log.info(f"Cleaning up {len(self._active_tasks)} tasks...")
            while self._active_tasks:
                await self._process_tasks(False)

    async def _process_tasks(self, first_task: bool):
        _, self._active_tasks = await asyncio.wait(
            self._active_tasks,
            timeout=self._loop_delay,
            return_when=(asyncio.FIRST_COMPLETED if first_task else asyncio.ALL_COMPLETED)
        )
        self._active_tasks = list(self._active_tasks)

    async def _batch_send(self, session) -> bool:
        metrics = []
        empty_queue_checks = 0
        max_empty_checks = 2
        while len(metrics) < self._max_messages_to_send and empty_queue_checks < max_empty_checks:
            try:
                # Build
                metric = self.messages.get_nowait()
                metrics.append(metric)
            except queue.Empty:
                empty_queue_checks += 1
                if empty_queue_checks < max_empty_checks:
                    await asyncio.sleep(self._message_wait_time)
        if metrics:
            self._active_tasks.append(asyncio.create_task(self._handle_metrics(metrics, session)))
            return True
        return False

    async def _handle_metrics(self, metrics: list, session):
        json_data = {"metrics": [metric.to_dict() for metric in metrics]}
        # If we are crashing, prevent a lot of retries
        if self._halt.is_set():
            self._max_retries = 1
        retries = self._max_retries
        retry_forever = self._max_retries == 0
        while retry_forever or retries > 0:
            try:
                async with session.post(self._endpoint, json=json_data, headers=self._headers) as resp:
                    resp.raise_for_status()
                    info = await resp.json()
                    if not info["status"] == "success":
                        for error in info["errors"]:
                            self._log.warning(f"Error from web API for metrics: {error}, retries: [{retries if not retry_forever else 'inf'}]")
                        if retries > 0:
                            retries -= 1
                        if self._halt.is_set():
                            break
                    else:
                        return True
            except Exception:
                retries -= 1
                self._log.exception(f"Exception while sending metrics, retries: [{retries if not retry_forever else 'inf'}]")
                await asyncio.sleep(self._retry_delay)
        self._log.error(f"Failure to send {len(metrics)} metrics, see logs for more details")
        return False


@injector.injectable_global
class ScriptMetrics:

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self._cache = {}
        self._lock = threading.RLock()
        self._sender = None
        self._log = zrlog.get_logger("erddaputil.metrics")
        if self.config.is_truthy(("erddaputil", "metrics_manager")):
            self._sender = load_object(self.config.get(("erddaputil", "metrics_manager")))()
            self._sender.start()
            self._log.notice(f"Metric collection enabled in daemon")
        else:
            self._log.notice(f"Metric collection disabled in daemon")

    def __cleanup__(self):
        self.halt()

    def halt(self):
        if self._sender:
            self._sender.terminate()
            self._sender.join()

    def send_message(self, metric: _Metric):
        if self._sender:
            self._sender.send_message(metric)

    def enum(self, name: str, description: str = "") -> _ScriptEnumMetric:
        return self._cached_metric(_ScriptEnumMetric, name, description=description)

    def info(self, name: str, description: str = "") -> _ScriptInfoMetric:
        return self._cached_metric(_ScriptInfoMetric, name, description=description)

    def counter(self, name: str, labels: dict = None, description: str = "") -> _ScriptCounterMetric:
        return self._cached_metric(_ScriptCounterMetric, name, labels=labels, description=description)

    def gauge(self, name: str, labels: dict = None, description: str = "") -> _ScriptGaugeMetric:
        return self._cached_metric(_ScriptGaugeMetric, name, labels=labels, description=description)

    def summary(self, name: str, labels: dict = None, description: str = "") -> _ScriptSummaryMetric:
        return self._cached_metric(_ScriptSummaryMetric, name, labels=labels, description=description)

    def histogram(self, name: str, labels: dict = None, description: str = "") -> _ScriptHistogramMetric:
        return self._cached_metric(_ScriptHistogramMetric, name, labels=labels, description=description)

    def _cached_metric(self, metric_cls: type, name: str, *args, labels: dict = None, **kwargs):
        label_key = "" if not labels else ("__" + "__".join(f"{x}_{labels[x]}" for x in labels.keys()))
        key_name = f"{metric_cls.__name__}__{name}{label_key}"
        if key_name not in self._cache:
            with self._lock:
                if key_name not in self._cache:
                    self._cache[key_name] = metric_cls(self, name, *args, labels=labels, **kwargs)
        return self._cache[key_name]
