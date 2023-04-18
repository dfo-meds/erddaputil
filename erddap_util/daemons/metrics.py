from autoinject import injector
import threading
import queue
import zirconium as zr
import logging
import aiohttp
import asyncio
from erddap_util.util.common import load_object


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


class _ScriptMetric:

    def __init__(self, metric_type, metric_parent, name, labels=None, description=""):
        self.metric_type = metric_type
        self.parent = metric_parent
        self.name = name
        self.labels = labels
        self.description = description

    def send_message(self, method, **kwargs):
        self.parent.send_message(_Metric(self.metric_type, self.name, self.labels, self.description, method, kwargs))


class _ScriptCounterMetric(_ScriptMetric):

    def __init__(self, *args, **kwargs):
        super().__init__('counter', *args, **kwargs)

    def increment(self, amount=1, exemplar=None):
        self.send_message('inc', amount=amount, exemplar=exemplar)


class _ScriptGaugeMetric(_ScriptMetric):

    def __init__(self, *args, **kwargs):
        super().__init__('gauge', *args, **kwargs)

    def increment(self, value=1):
        pass

    def decrement(self, value=1):
        pass

    def set(self, value):
        pass


class _ScriptSummaryMetric(_ScriptMetric):

    def __init__(self, *args, **kwargs):
        super().__init__('summary', *args, **kwargs)

    def observe(self, value):
        pass


class _ScriptHistogramMetric(_ScriptMetric):

    def __init__(self, *args, **kwargs):
        super().__init__('histogram', *args, **kwargs)

    def observe(self, value, exemplar=None):
        pass


class _ScriptInfoMetric(_ScriptMetric):

    def __init__(self, *args, **kwargs):
        super().__init__('info', *args, **kwargs)

    def info(self, key, value):
        pass


class _ScriptEnumMetric(_ScriptMetric):

    def __init__(self, *args, **kwargs):
        super().__init__('enum', *args, **kwargs)

    def state(self, state_name):
        pass


class LocalPrometheusSendThread(threading.Thread):

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        super().__init__()
        self.messages = queue.SimpleQueue()
        self._halt = threading.Event()
        self._wait_time = self.config.as_float(("erddaputil", "localprom", "delay_seconds"), default=0.25)
        host = self.config.as_str(("erddaputil", "localprom", "host"), default="localhost")
        port = self.config.as_int(("erddaputil", "localprom", "port"), default=5000)
        self._endpoint = self.config.as_str(("erddaputil", "localprom", "metrics_path"), default=f"http://{host}:{port}/push")
        self._log = logging.getLogger("erddaputil.localprom")
        self._send_headers = {
            'Authorization': f'bearer {self.config.get("erddaputil", "metrics", "security_secret")}'
        }
        self._max_concurrent_tasks = self.config.as_int(("erddaputil", "localprom", "max_tasks"), default=5)
        self._max_messages_to_send = self.config.as_int(("erddaputil", "localprom", "batch_size"), default=10)
        self._message_wait_time = self.config.as_float(("erddaputil", "localprom", "batch_wait_seconds"), default=1)
        self._max_retries = self.config.as_int(("erddaputil", "localprom", "max_retries"), default=30)
        self._retry_delay = self.config.as_float(("erddaputil", "localprom", "retry_delay_seconds"), default=15)
        self._active_tasks = []
        self.daemon = True

    def halt(self):
        self._halt.set()

    def send_message(self, metric: _Metric):
        if self._halt.is_set():
            return False
        self.messages.put_nowait(metric)
        return True

    @injector.as_thread_run
    def run(self):
        return asyncio.run(self._async_entry_point())

    async def _handle_metrics(self, metrics: list, session):
        json_data = {"metrics": [metric.to_dict() for metric in metrics]}
        retries = self._max_retries
        retry_forever = self._max_retries == 0
        while retry_forever or retries > 0:
            async with session.post(self._endpoint, json=json_data, headers=self._send_headers) as resp:
                info = await resp.json()
                if not info["status"] == "success":
                    for error in info["errors"]:
                        self._log.error(error)
                    if retries > 0:
                        retries -= 1
                else:
                    return
            await asyncio.sleep(self._retry_delay)

    async def _batch_send(self, session) -> bool:
        metrics = []
        waited_one = False
        # Round one
        while len(metrics) < self._max_messages_to_send:
            try:
                metric = self.messages.get_nowait()
                metrics.append(metric)
                continue
            except queue.Empty:
                if self._message_wait_time > 0 and not waited_one:
                    waited_one = True
                    await asyncio.sleep(self._message_wait_time)
                    continue
                break
        if metrics:
            self._active_tasks.append(asyncio.create_task(self._handle_metrics(metrics, session)))
            return True
        return False

    async def _async_entry_point(self):
        async with aiohttp.ClientSession() as session:
            while True:
                if self._halt.is_set():
                    while not self.messages.empty():
                        if not self._batch_send(session):
                            break
                    break
                while len(self._active_tasks) < self._max_concurrent_tasks and not self.messages.empty():
                    await self._batch_send(session)
                if self._active_tasks:
                    _, self._active_tasks = await asyncio.wait(self._active_tasks, timeout=self._wait_time, return_when=asyncio.FIRST_COMPLETED)
                else:
                    await asyncio.sleep(self._wait_time)
            self._log.out(f"Cleaning up {len(self._active_tasks)} tasks...")
            while self._active_tasks:
                _, self._active_tasks = await asyncio.wait(self._active_tasks, timeout=self._wait_time, return_when=asyncio.ALL_COMPLETED)


@injector.injectable_global
class ScriptMetrics:

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self._cache = {}
        self._lock = threading.RLock()
        self._sender = None
        if self.config.is_truthy(("erddaputil", "metrics", "sender")):
            self._sender = load_object(self.config.get(("erddaputil", "metrics", "sender")))()
            self._sender.start()

    def __cleanup__(self):
        self.halt()

    def halt(self):
        if self._sender:
            self._sender.halt()
            self._sender.join()

    def send_message(self, metric: _Metric):
        if self._sender:
            self._sender.send_message(metric)

    def enum(self, name: str) -> _ScriptEnumMetric:
        return self._cached_metric(_ScriptEnumMetric, name)

    def info(self, name: str) -> _ScriptInfoMetric:
        return self._cached_metric(_ScriptInfoMetric, name)

    def counter(self, name: str, labels: dict = None) -> _ScriptCounterMetric:
        return self._cached_metric(_ScriptCounterMetric, name, labels=labels)

    def gauge(self, name: str, labels: dict = None) -> _ScriptGaugeMetric:
        return self._cached_metric(_ScriptCounterMetric, name, labels=labels)

    def summary(self, name: str, labels: dict = None) -> _ScriptSummaryMetric:
        return self._cached_metric(_ScriptSummaryMetric, name, labels=labels)

    def histogram(self, name: str, labels: dict = None) -> _ScriptHistogramMetric:
        return self._cached_metric(_ScriptHistogramMetric, name, labels=labels)

    def _cached_metric(self, metric_cls: type, name: str, *args, labels: dict = None, **kwargs):
        label_key = "" if not labels else ("__" + "__".join(f"{x}_{labels[x]}" for x in labels.keys()))
        key_name = f"{metric_cls.__name__}__{name}{label_key}"
        if key_name not in self._cache:
            with self._lock:
                if key_name not in self._cache:
                    self._cache[key_name] = metric_cls(self, name, *args, labels=labels, **kwargs)
        return self._cache[key_name]
