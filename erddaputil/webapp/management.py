import flask
from .common import require_login
from erddaputil.main.commands import CommandResponse
import functools
import logging
from werkzeug.exceptions import HTTPException

bp = flask.Blueprint("management", __name__)


def error_shield(fn):

    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            resp = fn(*args, **kwargs)
            if resp is None:
                return {"success": True, "message": ""}, 200
            elif resp.state == 'success':
                return {"success": True, "message": resp.message}, 200
            else:
                return {"success": False, "message": resp.message}, 200
        except HTTPException as ex:
            return {"success": False, "message": str(ex)}, ex.code
        except Exception as ex:
            logging.getLogger("erddaputil.webapp").exception(ex)
            return {"success": False, "message": f"{type(ex).__name__}: {str(ex)}"}, 500

    return wrapped


def _map_dataset_ids(ds_id_list, cb, *args, **kwargs):
    messages = {}
    has_errors = False
    for ds_id in ds_id_list:
        resp = cb(ds_id, *args, **kwargs)
        messages[ds_id] = resp.message
        if resp.state != 'success':
            has_errors = True
    return CommandResponse(messages, 'error' if has_errors else 'success')


@bp.route("/datasets/reload", methods=["POST"])
@error_shield
@require_login
def reload_dataset():
    from erddaputil.erddap.commands import reload_dataset, reload_all_datasets
    body = flask.request.json
    if "flag" not in body:
        body["flag"] = 0
    elif body["flag"] not in (0, 1, 2):
        raise ValueError("Invalid flag")
    if "dataset_id" not in body:
        return reload_all_datasets(flag=body["flag"])
    elif isinstance(body["dataset_id"], str):
        return reload_dataset(body['dataset_id'], flag=body['flag'])
    else:
        return _map_dataset_ids(body['dataset_id'], reload_dataset, flag=body['flag'])


@bp.route("/datasets/activate", methods=["POST"])
@error_shield
@require_login
def activate_dataset():
    from erddaputil.erddap.commands import activate_dataset
    body = flask.request.json
    if "dataset_id" not in body:
        raise ValueError("Dataset ID required")
    elif isinstance(body["dataset_id"], str):
        return activate_dataset(body["dataset_id"])
    else:
        return _map_dataset_ids(body['dataset_id'], activate_dataset)


@bp.route("/datasets/deactivate", methods=["POST"])
@error_shield
@require_login
def deactivate_dataset():
    from erddaputil.erddap.commands import deactivate_dataset
    body = flask.request.json
    if "dataset_id" not in body:
        raise ValueError("Dataset ID required")
    elif isinstance(body["dataset_id"], str):
        return deactivate_dataset(body["dataset_id"])
    else:
        return _map_dataset_ids(body['dataset_id'], deactivate_dataset)


@bp.route("/datasets/compile", methods=["POST"])
@error_shield
@require_login
def compile_datasets():
    from erddaputil.erddap.commands import compile_datasets
    return compile_datasets()


@bp.route("/block/ip", methods=["POST"])
@error_shield
@require_login
def block_ip():
    from erddaputil.erddap.commands import block_ip
    if "ip" not in flask.request.json:
        raise flask.abort(400)
    return block_ip(flask.request.json["ip"])


@bp.route("/block/email", methods=["POST"])
@error_shield
@require_login
def block_email():
    from erddaputil.erddap.commands import block_email
    if "email" not in flask.request.json:
        raise flask.abort(400)
    return block_email(flask.request.json["email"])


@bp.route("/allow/unlimited", methods=["POST"])
@error_shield
@require_login
def allow_unlimited():
    from erddaputil.erddap.commands import allow_unlimited
    if "ip" not in flask.request.json:
        raise flask.abort(400)
    return allow_unlimited(flask.request.json["ip"])

