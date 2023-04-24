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


@bp.route("/reload-dataset/<dataset_id>/<int:flag>", method=["POST"])
@require_login
@error_shield
def reload_dataset(dataset_id, flag):
    from erddaputil.erddap.commands import reload_dataset
    if flag not in (0, 1, 2):
        return flask.abort(404)
    return reload_dataset(dataset_id, flag=flag)


@bp.route("/activate-dataset/<dataset_id>", method=["POST"])
@require_login
@error_shield
def activate_dataset(dataset_id):
    from erddaputil.erddap.commands import activate_dataset
    return activate_dataset(dataset_id)


@bp.route("/deactivate-dataset/<dataset_id>", method=["POST"])
@require_login
@error_shield
def deactivate_dataset(dataset_id):
    from erddaputil.erddap.commands import deactivate_dataset
    return deactivate_dataset(dataset_id)


@bp.route("/reload-all-datasets/<int:flag>", method=["POST"])
@require_login
@error_shield
def reload_all_datasets(flag):
    from erddaputil.erddap.commands import reload_all_datasets
    if flag not in (0, 1, 2):
        return flask.abort(404)
    return reload_all_datasets(flag)


@bp.route("/compile-datasets", method=["POST"])
@require_login
@error_shield
def compile_datasets():
    from erddaputil.erddap.commands import compile_datasets
    return compile_datasets()


@bp.route("/block-ip", method=["POST"])
@require_login
@error_shield
def block_ip():
    from erddaputil.erddap.commands import block_ip
    if "ip" not in flask.request.json:
        raise flask.abort(400)
    return block_ip(flask.request.json["ip"])


@bp.route("/block-email", method=["POST"])
@require_login
@error_shield
def block_email():
    from erddaputil.erddap.commands import block_email
    if "email" not in flask.request.json:
        raise flask.abort(400)
    return block_email(flask.request.json["email"])


@bp.route("/allow-unlimited", method=["POST"])
@require_login
@error_shield
def allow_unlimited():
    from erddaputil.erddap.commands import allow_unlimited
    if "ip" not in flask.request.json:
        raise flask.abort(400)
    return allow_unlimited(flask.request.json["ip"])

