import flask
from prometheus_client import Counter, Gauge, Histogram, Summary, Enum, Info
from autoinject import injector
from threading import RLock
from .common import require_login, time_with_errors
import zrlog

bp = flask.Blueprint("metrics", __name__)

PROM_METRICS = Counter("erddaputil_webapp_individual_metrics_pushed", "Number of metrics pushed to the ERDDAPUtil endpoint", labelnames=("result",))
PROM_METRIC_REQUESTS = Summary("erddaputil_webapp_metric_push", "Time to execute a metric push", labelnames=["result"])


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
        self._log = zrlog.get_logger("erddaputil.webapp.metrics")

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
        elif type_name == "gauge":
            metric = Gauge(metric_name, description, [str(x) for x in labels.keys()])
        elif type_name == "summary":
            metric = Summary(metric_name, description, [str(x) for x in labels.keys()])
        elif type_name == 'histogram':
            buckets = kwargs.pop('_buckets', default=None)
            metric = Histogram(metric_name, description, [str(x) for x in labels.keys()], buckets=buckets)
        elif type_name == 'info':
            metric = Info(metric_name, description, [str(x) for x in labels.keys()])
        elif type_name == 'enum':
            metric = Enum(metric_name, description, [str(x) for x in labels.keys()])
        if metric is None:
            raise ValueError(f"Invalid metric type: {type_name}")
        return PromMetricWrapper(metric, use_labels)


@bp.route("/push", methods=["POST"])
@time_with_errors(PROM_METRIC_REQUESTS)
@require_login
@injector.inject
def handle_metrics(wc_metrics: WebCollectedMetrics = None):
    """Endpoint for metric collection"""
    errors = []
    result = "success"
    if "metrics" in flask.request.json:
        for json_metric in flask.request.json.get("metrics"):
            try:
                wc_metrics.handle_request(**json_metric)
                PROM_METRICS.labels(result="success").inc()
            except Exception as ex:
                zrlog.get_logger("erddaputil.webapp.metrics").exception(f"Exception processing metric {json_metric}")
                errors.append(str(ex))
                result = "error"
                PROM_METRICS.labels(result="error").inc()
    else:
        try:
            wc_metrics.handle_request(**flask.request.json)
            PROM_METRICS.labels(result="success").inc()
        except Exception as ex:
            zrlog.get_logger("erddaputil.webapp.metrics").exception(f"Exception processing metric {flask.request.json}")
            errors.append(str(ex))
            result = "error"
            PROM_METRICS.labels(result="error").inc()
            flask.jsonify()
    return {'errors': errors, 'success': result == 'success'}


