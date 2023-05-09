from erddaputil.main import CommandGroup
from autoinject import injector
from .datasets import ErddapDatasetManager
from erddaputil.main import CommandResponse

cg = CommandGroup()


def flush_logs(_broadcast: bool = True):
    return cg.remote_command("flush_logs", _broadcast=_broadcast)


def list_datasets():
    return cg.remote_command("list_datasets", _broadcast=False)


def reload_dataset(dataset_id: str, flag: int = 0, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("reload_datasets", dataset_id=dataset_id, flag=flag, flush=flush, _broadcast=_broadcast)


def activate_dataset(dataset_id: str, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("set_active_flag", dataset_id=dataset_id, active_flag=True, flush=flush, _broadcast=_broadcast)


def deactivate_dataset(dataset_id: str, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("set_active_flag", dataset_id=dataset_id, active_flag=False, flush=flush, _broadcast=_broadcast)


def reload_all_datasets(flag: int = 0, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("reload_all_datasets", flag=flag, flush=flush, _broadcast=_broadcast)


def clear_erddap_cache(dataset_id: str = None, _broadcast: bool = True):
    return cg.remote_command('clear_erddap_cache', dataset_id=dataset_id or "", _broadcast=_broadcast)


def block_email(email_address, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("manage_email_block_list", email_address=email_address, block=True, flush=flush, _broadcast=_broadcast)


def block_ip(ip_address, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("manage_ip_block_list", ip_address=ip_address, block=True, flush=flush, _broadcast=_broadcast)


def allow_unlimited(ip_address, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("manage_unlimited_allow_list", ip_address=ip_address, allow=True, flush=flush, _broadcast=_broadcast)


def unblock_email(email_address, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("manage_email_block_list", email_address=email_address, block=False, flush=flush, _broadcast=_broadcast)


def unblock_ip(ip_address, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("manage_ip_block_list", ip_address=ip_address, block=False, flush=flush, _broadcast=_broadcast)


def unallow_unlimited(ip_address, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("manage_unlimited_allow_list", ip_address=ip_address, allow=False, flush=flush, _broadcast=_broadcast)


def compile_datasets(skip_errored_datasets: bool = None, reload_all_datasets: bool = False, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command(
        "compile_datasets",
        skip_errored_datasets=skip_errored_datasets,
        reload_all_datasets=reload_all_datasets,
        immediate=flush,
        _broadcast=_broadcast
    )


@cg.route("list_datasets")
@injector.inject
def _clear_erddap_cache(*args, edm: ErddapDatasetManager = None, **kwargs):
    ds_list = edm.list_datasets()
    return CommandResponse(ds_list, 'success')


@cg.route("flush_logs")
@injector.inject
def _flush_logs(*args, edm: ErddapDatasetManager = None, **kwargs):
    edm.flush_logs()
    return True


@cg.route("clear_erddap_cache")
@injector.inject
def _clear_erddap_cache(*args, edm: ErddapDatasetManager = None, **kwargs):
    edm.clear_erddap_cache(*args, **kwargs)
    return True


@cg.route("reload_all_datasets")
@injector.inject
def _reload_all_datasets(*args, edm: ErddapDatasetManager = None, **kwargs):
    edm.reload_all_datasets(*args, **kwargs)
    return True


@cg.route("compile_datasets")
@injector.inject
def _compile_datasets(*args, edm: ErddapDatasetManager = None, **kwargs):
    edm.compile_datasets(*args, **kwargs)
    return True


@cg.route("set_active_flag")
@injector.inject
def _set_active_flag(*args, edm: ErddapDatasetManager = None, **kwargs):
    edm.set_active_flag(*args, **kwargs)
    return True


@cg.route("manage_email_block_list")
@injector.inject
def _block_email(*args, edm: ErddapDatasetManager = None, **kwargs):
    edm.update_email_block_list(*args, **kwargs)
    return True


@cg.route("manage_ip_block_list")
@injector.inject
def _block_ip(*args, edm: ErddapDatasetManager = None, **kwargs):
    edm.update_ip_block_list(*args, **kwargs)
    return True


@cg.route("manage_unlimited_allow_list")
@injector.inject
def _allow_unlimited(*args, edm: ErddapDatasetManager = None, **kwargs):
    edm.update_allow_unlimited_list(*args, **kwargs)
    return True


@cg.route("reload_datasets")
@injector.inject
def _reload_dataset(*args, edm: ErddapDatasetManager = None, **kwargs):
    edm.reload_dataset(*args, **kwargs)
    return True


@cg.on_tidy
@injector.inject
def _do_tidy(edm: ErddapDatasetManager = None):
    edm.flush(False)


@cg.on_shutdown
@injector.inject
def _do_shutdown(edm: ErddapDatasetManager = None):
    edm.flush(True)
