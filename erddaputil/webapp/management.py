import flask
from .common import require_login, time_with_errors, error_shield
from erddaputil.main.commands import CommandResponse
from prometheus_client import Summary

bp = flask.Blueprint("management", __name__)


def _map_dataset_ids(ds_id_list, cb, *args, **kwargs):
    messages = {}
    has_errors = False
    for ds_id in ds_id_list:
        resp = cb(ds_id, *args, **kwargs)
        messages[ds_id] = resp.message
        if resp.state != 'success':
            has_errors = True
    return CommandResponse(messages, 'error' if has_errors else 'success')


DATASET_RELOAD = Summary('erddaputil_webapp_dataset_reload', 'Time to reload a dataset', labelnames=["result"])


@bp.route("/datasets/reload", methods=["POST"])
@time_with_errors(DATASET_RELOAD)
@error_shield
@require_login
def reload_dataset():
    from erddaputil.erddap.commands import reload_dataset, reload_all_datasets
    body = flask.request.json
    if "_broadcast" not in body:
        body["_broadcast"] = 1
    elif body["_broadcast"] not in (0, 1, 2, "1", "2", "0"):
        raise ValueError("Invalid broadcast flag")
    if "flag" not in body:
        body["flag"] = 0
    elif body["flag"] not in (0, 1, 2):
        raise ValueError("Invalid flag")
    if "dataset_id" not in body or not body["dataset_id"]:
        return reload_all_datasets(flag=body["flag"], _broadcast=int(body["_broadcast"]))
    else:
        return reload_dataset(body['dataset_id'], flag=body['flag'], _broadcast=int(body["_broadcast"]))


DATASET_ACTIVATE = Summary('erddaputil_webapp_dataset_activation', 'Time to activate a dataset', labelnames=["result"])


@bp.route("/datasets/activate", methods=["POST"])
@time_with_errors(DATASET_ACTIVATE)
@error_shield
@require_login
def activate_dataset():
    from erddaputil.erddap.commands import activate_dataset
    body = flask.request.json
    if "_broadcast" not in body:
        body["_broadcast"] = 1
    elif body["_broadcast"] not in (0, 1, 2, "1", "2", "0"):
        raise ValueError("Invalid broadcast flag")
    if "dataset_id" not in body:
        raise ValueError("Dataset ID required")
    return activate_dataset(body["dataset_id"], _broadcast=int(body["_broadcast"]))


DATASET_DEACTIVATE = Summary('erddaputil_webapp_dataset_deactivation', 'Time to deactivate a dataset', labelnames=["result"])


@bp.route("/datasets/deactivate", methods=["POST"])
@time_with_errors(DATASET_DEACTIVATE)
@error_shield
@require_login
def deactivate_dataset():
    from erddaputil.erddap.commands import deactivate_dataset
    body = flask.request.json
    if "_broadcast" not in body:
        body["_broadcast"] = 1
    elif body["_broadcast"] not in (0, 1, 2, "1", "2", "0"):
        raise ValueError("Invalid broadcast flag")
    if "dataset_id" not in body:
        raise ValueError("Dataset ID required")
    return deactivate_dataset(body["dataset_id"], _broadcast=int(body["_broadcast"]))


LOG_FLUSH = Summary('erddaputil_webapp_flush_logs', 'Time to flush logs', labelnames=["result"])


@bp.route("/flush-logs", methods=["POST"])
@time_with_errors(LOG_FLUSH)
@error_shield
@require_login
def flush_logs():
    from erddaputil.erddap.commands import flush_logs
    body = flask.request.json or {}
    if "_broadcast" not in body:
        body["_broadcast"] = 1
    elif body["_broadcast"] not in (0, 1, 2, "1", "2", "0"):
        raise ValueError("Invalid broadcast flag")
    return flush_logs(_broadcast=int(body["_broadcast"]))


LIST_DATASETS = Summary('erddaputil_webapp_list_datasets', 'Time to list datasets', labelnames=["result"])


@bp.route("/datasets", methods=["GET"])
@time_with_errors(LIST_DATASETS)
@require_login
def list_datasets():
    from erddaputil.erddap.commands import list_datasets
    ds_resp = list_datasets()
    item_list = ds_resp.message.split("\n")
    return {
        'success': True,
        'message': item_list[0],
        'datasets': item_list[1:]
    }, 200


CLEAR_CACHE = Summary('erddaputil_webapp_clear_cache', 'Time to clear the cache', labelnames=["result"])


@bp.route("/clear-cache", methods=["POST"])
@time_with_errors(CLEAR_CACHE)
@error_shield
@require_login
def clear_cache():
    from erddaputil.erddap.commands import clear_erddap_cache
    body = flask.request.json or {}
    if "_broadcast" not in body:
        body["_broadcast"] = 1
    elif body["_broadcast"] not in (0, 1, 2, "1", "2", "0"):
        raise ValueError("Invalid broadcast flag")
    if "dataset_id" not in body:
        return clear_erddap_cache("", _broadcast=int(body["_broadcast"]))
    return clear_erddap_cache(body["dataset_id"], _broadcast=int(body["_broadcast"]))


COMPILE_DATASETS = Summary('erddaputil_webapp_compile_datasets', 'Time to compile the datasets', labelnames=["result"])


@bp.route("/datasets/compile", methods=["POST"])
@time_with_errors(COMPILE_DATASETS)
@error_shield
@require_login
def compile_datasets():
    from erddaputil.erddap.commands import compile_datasets
    body = flask.request.json or {}
    if "_broadcast" not in body:
        body["_broadcast"] = 1
    elif body["_broadcast"] not in (0, 1, 2, "1", "2", "0"):
        raise ValueError("Invalid broadcast flag")
    return compile_datasets(_broadcast=int(body["_broadcast"]))


BLOCK_IP = Summary('erddaputil_webapp_block_ip', 'Time to block an IP address', labelnames=["result"])


@bp.route("/block/ip", methods=["POST"])
@time_with_errors(BLOCK_IP)
@error_shield
@require_login
def block_ip():
    from erddaputil.erddap.commands import block_ip
    body = flask.request.json or {}
    if "_broadcast" not in body:
        body["_broadcast"] = 1
    elif body["_broadcast"] not in (0, 1, 2, "1", "2", "0"):
        raise ValueError("Invalid broadcast flag")
    if "ip" not in body:
        raise flask.abort(400)
    return block_ip(body["ip"], _broadcast=int(body["_broadcast"]))


BLOCK_EMAIL = Summary('erddaputil_webapp_block_email', 'Time to block an email address', labelnames=["result"])


@bp.route("/block/email", methods=["POST"])
@time_with_errors(BLOCK_EMAIL)
@error_shield
@require_login
def block_email():
    from erddaputil.erddap.commands import block_email
    body = flask.request.json or {}
    if "_broadcast" not in body:
        body["_broadcast"] = 1
    elif body["_broadcast"] not in (0, 1, 2, "1", "2", "0"):
        raise ValueError("Invalid broadcast flag")
    if "email" not in body:
        raise flask.abort(400)
    return block_email(body["email"], _broadcast=int(body["_broadcast"]))


ALLOW_UNLIMITED = Summary('erddaputil_webapp_allow_unlimited', 'Time to allow an IP address unlimited access', labelnames=["result"])


@bp.route("/allow/unlimited", methods=["POST"])
@time_with_errors(ALLOW_UNLIMITED)
@error_shield
@require_login
def allow_unlimited():
    from erddaputil.erddap.commands import allow_unlimited
    body = flask.request.json or {}
    if "_broadcast" not in body:
        body["_broadcast"] = 1
    elif body["_broadcast"] not in (0, 1, 2, "1", "2", "0"):
        raise ValueError("Invalid broadcast flag")
    if "ip" not in body:
        raise flask.abort(400)
    return allow_unlimited(body["ip"], _broadcast=int(body["_broadcast"]))


UNBLOCK_IP = Summary('erddaputil_webapp_unblock_ip', 'Time to unblock an ip address', labelnames=["result"])


@bp.route("/unblock/ip", methods=["POST"])
@time_with_errors(UNBLOCK_IP)
@error_shield
@require_login
def unblock_ip():
    from erddaputil.erddap.commands import unblock_ip
    body = flask.request.json or {}
    if "_broadcast" not in body:
        body["_broadcast"] = 1
    elif body["_broadcast"] not in (0, 1, 2, "1", "2", "0"):
        raise ValueError("Invalid broadcast flag")
    if "ip" not in body:
        raise flask.abort(400)
    return unblock_ip(body["ip"], _broadcast=int(body["_broadcast"]))


UNBLOCK_EMAIL = Summary('erddaputil_webapp_unblock_email', 'Time to unblock an email', labelnames=["result"])


@bp.route("/unblock/email", methods=["POST"])
@time_with_errors(UNBLOCK_EMAIL)
@error_shield
@require_login
def unblock_email():
    from erddaputil.erddap.commands import unblock_email
    body = flask.request.json or {}
    if "_broadcast" not in body:
        body["_broadcast"] = 1
    elif body["_broadcast"] not in (0, 1, 2, "1", "2", "0"):
        raise ValueError("Invalid broadcast flag")
    if "email" not in body:
        raise flask.abort(400)
    return unblock_email(body["email"], _broadcast=int(body["_broadcast"]))


UNALLOW_UNLIMITED = Summary('erddaputil_webapp_unallow_unlimited', 'Time to unallow an unlimited IP', labelnames=["result"])


@bp.route("/unallow/unlimited", methods=["POST"])
@time_with_errors(UNALLOW_UNLIMITED)
@error_shield
@require_login
def unallow_unlimited():
    from erddaputil.erddap.commands import unallow_unlimited
    body = flask.request.json or {}
    if "_broadcast" not in body:
        body["_broadcast"] = 1
    elif body["_broadcast"] not in (0, 1, 2, "1", "2", "0"):
        raise ValueError("Invalid broadcast flag")
    if "ip" not in body:
        raise flask.abort(400)
    return unallow_unlimited(body["ip"], _broadcast=int(body["_broadcast"]))
