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

    def handle_request(self, metric_type: str, metric_name: str, labels: dict, description: str, method: str, arguments: dict):
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
        self._metrics[key].handle_request(labels=labels, method=method, **arguments)

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


@app.route("/health", methods=["GET"])
def health_check():
    return "healthy", 200


@app.route("/push", methods=["POST"])
@injector.inject
def handle_metrics(config: zr.ApplicationConfig = None, wc_metrics: WebCollectedMetrics = None):
    ah = flask.request.headers.get("Authorization", default=None)
    if ah is None:
        return {"status": 'error', 'errors': ['access denied']}, 403
    if not ah[0:7].lower() == 'bearer ':
        return {"status": 'error', 'errors': ['access denied']}, 403
    token = ah[7].strip("\r\n\t ")
    if token != config.get(("erddaputil", "metrics", "security_secret"), default=""):
        return {"status": 'error', 'errors': ['access denied']}, 403
    errors = []
    result = "success"
    if "metrics" in flask.request.json:
        for json_metric in flask.request.json.get("metrics"):
            try:
                wc_metrics.handle_request(**json_metric)
            except Exception as ex:
                errors.append(str(ex))
                result = "error"
    else:
        try:
            wc_metrics.handle_request(**flask.request.json)
        except Exception as ex:
            errors.append(str(ex))
            result = "error"
    return {'status': result, 'errors': errors}, 200 if result == 'success' else 500

