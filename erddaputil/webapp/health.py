import flask

bp = flask.Blueprint("health", __name__)


@bp.route("/health", methods=["GET"])
def health_check():
    return "healthy", 200

