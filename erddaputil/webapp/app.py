import flask
import zirconium as zr
from autoinject import injector
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app
from erddaputil.common import init_config


def create_app():
    init_config()
    app = flask.Flask(__name__)
    init_app(app)
    return app


@injector.inject
def init_app(app, config: zr.ApplicationConfig = None):
    if "flask" in config:
        app.config.update(config["flask"])

    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
        "/metrics": make_wsgi_app()
    })

    from .health import bp as health_bp
    app.register_blueprint(health_bp)

    if config.as_bool(("erddaputil", "webapp", "enable_metrics_collector"), default=True):
        from .metrics import bp as metrics_bp
        app.register_blueprint(metrics_bp)

    if config.as_bool(("erddaputil", "webapp", "enable_management_api"), default=True):
        from .management import bp as man_bp
        app.register_blueprint(man_bp)

default_app = create_app()
