import flask
from .common import require_login

bp = flask.Blueprint("management", __name__)


def error_shield(fn):

    def wrapped(*args, **kwargs):
        try:
            resp = fn(*args, **kwargs)
            if resp.state == 'success':
                return {"success": True, "message": resp.message}, 200
            else:
                return {"success": False, "message": resp.message}, 200
        except Exception as ex:
            return {"success": False, "message": f"{type(ex)}: {str(ex)}"}, 500

    return wrapped


@bp.route("/reload_dataset/<dataset_id>/<int:flag>")
@require_login
@error_shield
def reload_dataset(dataset_id, flag):
    from erddaputil.erddap.commands import reload_dataset
    if flag not in (0, 1, 2):
        return flask.abort(404)
    return reload_dataset(dataset_id, flag=flag)
