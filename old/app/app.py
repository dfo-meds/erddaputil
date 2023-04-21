import flask
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
import zirconium as zr
from autoinject import injector


def create_app():
    from old.util.common import init_util
    init_util()
    app = flask.Flask(__name__)
    init_app(app)
    return app


@injector.inject
def init_app(app, config: zr.ApplicationConfig = None):
    if "flask" in config:
        app.config.update(config["flask"])

    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
        '/metrics': make_wsgi_app()
    })

    from .cli import cli
    app.cli.commands.update(cli.commands)

    from .metrics import bp
    app.register_blueprint(bp)

    return app
