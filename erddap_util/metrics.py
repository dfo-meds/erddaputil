from autoinject import injector
import threading
import queue
import zirconium as zr
import logging
import aiohttp
import asyncio


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


class _MetricSendThread(threading.Thread):

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        super().__init__()
        self.messages = queue.SimpleQueue()
        self._halt = False
        self._wait_time = 0.25
        self._endpoint = self.config.as_str(("erddaputil", "metrics_path"), "http://localhost:5000/push")
        self._log = logging.getLogger("erddaputil.sendmetrics")
        self._send_headers = {}
        self._max_concurrent_tasks = 10

    def halt(self):
        self._halt = True

    def send_message(self, metric: _Metric):
        if self._halt:
            return False
        self.messages.put_nowait(metric)
        return True

    @injector.as_thread_run
    def run(self):
        return asyncio.run(self._async_entry_point())

    async def _handle_metric(self, metric: _Metric, session):
        async with session.post(self._endpoint, json=metric.to_dict(), headers=self._send_headers) as resp:
            info = await resp.json()
            if not info["status"] == "success":
                logging.getLogger("erddaputil.metrics").error(info["error"])

    async def _async_entry_point(self):
        async with aiohttp.ClientSession() as session:
            active_tasks = []
            while True:
                try:
                    metric = self.messages.get_nowait()
                    active_tasks.append(asyncio.create_task(self._handle_metric(metric, session)))
                    if len(active_tasks) >= self._max_concurrent_tasks:
                        _, active_tasks = await asyncio.wait(active_tasks, timeout=self._wait_time, return_when=asyncio.FIRST_COMPLETED)
                except queue.Empty:
                    if self._halt:
                        break
                    if active_tasks:
                        # We can work on and update our tasks then here
                        _, active_tasks = await asyncio.wait(active_tasks, timeout=self._wait_time, return_when=asyncio.ALL_COMPLETED)
                    else:
                        await asyncio.sleep(self._wait_time)
            while active_tasks:
                logging.getLogger("erddaputil.metrics").out(f"Cleaning up {len(active_tasks)} tasks...")
                _, active_tasks = await asyncio.wait(active_tasks, timeout=self._wait_time, return_when=asyncio.ALL_COMPLETED)


@injector.injectable_global
class ScriptMetrics:

    def __init__(self):
        self._cache = {}
        self._lock = threading.RLock()
        self._sender = _MetricSendThread()
        self._sender.start()

    def __cleanup__(self):
        self.halt()

    def halt(self):
        self._sender.halt()
        self._sender.join()

    def send_message(self, metric: _Metric):
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
