import flask
from prometheus_client import make_wsgi_app, Counter
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from autoinject import injector
import zirconium as zr
from threading import RLock


class PromMetricWrapper:

    def __init__(self, metric, use_labels: bool = True):
        self._metric = metric
        self.use_labels = use_labels

    def handle_request(self, labels, method, **kwargs):
        metric = self._metric if not (self.use_labels and labels) else self._metric.labels(**labels)
        if not hasattr(metric, method):
            raise ValueError(f"No such method: {method}")
        getattr(metric, method)(**kwargs)


@injector.injectable_global
class WebCollectedMetrics:

    def __init__(self):
        self._metrics = {}
        self._lock = RLock()

    def handle_request(self, metric_type: str, metric_name: str, labels: dict, description: str, method: str, kwargs: dict):
        metric_type = metric_type.lower()
        metric_name = metric_name.lower()
        key = f"{metric_type}__{metric_name}"
        if key not in self._metrics:
            # Protect from two requests building the counter at the same time
            with self._lock:
                # Ensure it didn't get built while waiting for the lock
                if key not in self._metrics:
                    self._metrics[key] = self._build_metric(
                        metric_type.lower(),
                        metric_name=metric_name,
                        labels=labels,
                        description=description
                    )
        self._metrics[key].handle_request(labels=labels, method=method, **kwargs)

    def _build_metric(self, type_name, metric_name, description, labels, **kwargs):
        metric = None
        use_labels = True
        if type_name == "counter":
            metric = Counter(metric_name, description, [str(x) for x in labels.keys()])
        # TODO: other metric types)
        if metric is None:
            raise ValueError(f"Invalid metric type: {type_name}")
        return PromMetricWrapper(metric, use_labels)


app = flask.Flask(__name__)

from erddap_util.common import init_util
init_util([".erddaputil.app.yaml", ".erddaputil.app.toml"])

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})


@app.route("/push", methods=["POST"])
@injector.inject
def handle_metrics(config: zr.ApplicationConfig = None, wc_metrics: WebCollectedMetrics = None):
    try:
        # TODO: security options
        print(flask.request.json)
        wc_metrics.handle_request(
            metric_type=flask.request.json.pop('metric_type'),
            metric_name=flask.request.json.pop('metric_name'),
            labels=flask.request.json.pop('labels', {}),
            description=flask.request.json.pop('description', ''),
            method=flask.request.json.pop('method', ''),
            kwargs=flask.request.json.pop('arguments', {})
        )
        return {'status': 'success'}, 200
    except Exception as ex:
        return {'status': 'error', 'error': str(ex)}, 500
