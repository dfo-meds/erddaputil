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


DATASET_RELOAD = Summary('erddaputil_webapp_dataset_reload', 'Time to reload a dataset')


@bp.route("/datasets/reload", methods=["POST"])
@time_with_errors(DATASET_RELOAD)
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


DATASET_ACTIVATE = Summary('erddaputil_webapp_dataset_activation', 'Time to activate a dataset')


@bp.route("/datasets/activate", methods=["POST"])
@time_with_errors(DATASET_ACTIVATE)
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


DATASET_DEACTIVATE = Summary('erddaputil_webapp_dataset_deactivation', 'Time to deactivate a dataset')


@bp.route("/datasets/deactivate", methods=["POST"])
@time_with_errors(DATASET_DEACTIVATE)
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


LOG_FLUSH = Summary('erddaputil_webapp_flush_logs', 'Time to flush logs')


@bp.route("/flush-logs", methods=["POST"])
@time_with_errors(LOG_FLUSH)
@error_shield
@require_login
def flush_logs():
    from erddaputil.erddap.commands import flush_logs
    return flush_logs()


LIST_DATASETS = Summary('erddaputil_webapp_list_datasets', 'Time to list datasets')


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


CLEAR_CACHE = Summary('erddaputil_webapp_clear_cache', 'Time to clear the cache')


@bp.route("/clear-cache", methods=["POST"])
@time_with_errors(CLEAR_CACHE)
@error_shield
@require_login
def clear_cache():
    from erddaputil.erddap.commands import clear_erddap_cache
    body = flask.request.json
    if "dataset_id" not in body:
        return clear_erddap_cache("")
    elif isinstance(body["dataset_id"], str):
        return clear_erddap_cache(body["dataset_id"])
    else:
        return _map_dataset_ids(body['dataset_id'], clear_erddap_cache)


COMPILE_DATASETS = Summary('erddaputil_webapp_compile_datasets', 'Time to compile the datasets')


@bp.route("/datasets/compile", methods=["POST"])
@time_with_errors(COMPILE_DATASETS)
@error_shield
@require_login
def compile_datasets():
    from erddaputil.erddap.commands import compile_datasets
    return compile_datasets()


BLOCK_IP = Summary('erddaputil_webapp_block_ip', 'Time to block an IP address')


@bp.route("/block/ip", methods=["POST"])
@time_with_errors(BLOCK_IP)
@error_shield
@require_login
def block_ip():
    from erddaputil.erddap.commands import block_ip
    if "ip" not in flask.request.json:
        raise flask.abort(400)
    return block_ip(flask.request.json["ip"])


BLOCK_EMAIL = Summary('erddaputil_webapp_block_email', 'Time to block an email address')


@bp.route("/block/email", methods=["POST"])
@time_with_errors(BLOCK_EMAIL)
@error_shield
@require_login
def block_email():
    from erddaputil.erddap.commands import block_email
    if "email" not in flask.request.json:
        raise flask.abort(400)
    return block_email(flask.request.json["email"])


ALLOW_UNLIMITED = Summary('erddaputil_webapp_allow_unlimited', 'Time to allow an IP address unlimited access')


@bp.route("/allow/unlimited", methods=["POST"])
@time_with_errors(ALLOW_UNLIMITED)
@error_shield
@require_login
def allow_unlimited():
    from erddaputil.erddap.commands import allow_unlimited
    if "ip" not in flask.request.json:
        raise flask.abort(400)
    return allow_unlimited(flask.request.json["ip"])


UNBLOCK_IP = Summary('erddaputil_webapp_unblock_ip', 'Time to unblock an ip address')


@bp.route("/unblock/ip", methods=["POST"])
@time_with_errors(UNBLOCK_IP)
@error_shield
@require_login
def unblock_ip():
    from erddaputil.erddap.commands import unblock_ip
    if "ip" not in flask.request.json:
        raise flask.abort(400)
    return unblock_ip(flask.request.json["ip"])


UNBLOCK_EMAIL = Summary('erddaputil_webapp_unblock_email', 'Time to unblock an email')


@bp.route("/unblock/email", methods=["POST"])
@time_with_errors(UNBLOCK_EMAIL)
@error_shield
@require_login
def unblock_email():
    from erddaputil.erddap.commands import unblock_email
    if "email" not in flask.request.json:
        raise flask.abort(400)
    return unblock_email(flask.request.json["email"])


UNALLOW_UNLIMITED = Summary('erddaputil_webapp_unallow_unlimited', 'Time to unallow an unlimited IP')


@bp.route("/unallow/unlimited", methods=["POST"])
@time_with_errors(UNALLOW_UNLIMITED)
@error_shield
@require_login
def unallow_unlimited():
    from erddaputil.erddap.commands import unallow_unlimited
    if "ip" not in flask.request.json:
        raise flask.abort(400)
    return unallow_unlimited(flask.request.json["ip"])
