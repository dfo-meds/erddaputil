"""ERDDAP Command wrappers

Each command is implemented as a function (with no underscore prefix) that
creates and sends a command to the daemon. The daemon unpacks the arguments
and calls the underscore-prefixed version which passes it to the appropriate
class.
"""
from erddaputil.main import CommandGroup
from autoinject import injector
from .datasets import ErddapDatasetManager
from erddaputil.main import CommandResponse

cg = CommandGroup()


def flush_logs(_broadcast: int = 1):
    """Flush logs wrapper"""
    return cg.remote_command("flush_logs", _broadcast=_broadcast)


@cg.route("flush_logs")
@injector.inject
def _flush_logs(*args, edm: ErddapDatasetManager = None, **kwargs):
    """Flush logs handler"""
    edm.flush_logs()
    return True


def list_datasets():
    """List datasets wrapper"""
    return cg.remote_command("list_datasets", _broadcast=0)


@cg.route("list_datasets")
@injector.inject
def _list_datasets(*args, edm: ErddapDatasetManager = None, **kwargs):
    """List datasets handler"""
    ds_list = edm.list_datasets()
    return CommandResponse(ds_list, 'success')


def reload_dataset(dataset_id: str, flag: int = 0, flush: bool = False, _broadcast: int = 1):
    """Reload dataset wrapper"""
    return cg.remote_command("reload_datasets", dataset_id=dataset_id, flag=flag, flush=flush, _broadcast=_broadcast)


@cg.route("reload_datasets")
@injector.inject
def _reload_dataset(*args, edm: ErddapDatasetManager = None, **kwargs):
    """Reload dataset handler"""
    edm.reload_dataset(*args, **kwargs)
    return True


def activate_dataset(dataset_id: str, flush: bool = False, _broadcast: int = 1):
    """Set active flag TRUE wrapper"""
    return cg.remote_command("set_active_flag", dataset_id=dataset_id, active_flag=True, flush=flush, _broadcast=_broadcast)


def deactivate_dataset(dataset_id: str, flush: bool = False, _broadcast: int = 1):
    """Set active flag FALSE wrapper"""
    return cg.remote_command("set_active_flag", dataset_id=dataset_id, active_flag=False, flush=flush, _broadcast=_broadcast)


@cg.route("set_active_flag")
@injector.inject
def _set_active_flag(*args, edm: ErddapDatasetManager = None, **kwargs):
    """Set active flag handler"""
    edm.set_active_flag(*args, **kwargs)
    return True


def reload_all_datasets(flag: int = 0, flush: bool = False, _broadcast: int = 1):
    """Reload all datasets wrapper"""
    return cg.remote_command("reload_all_datasets", flag=flag, flush=flush, _broadcast=_broadcast)


@cg.route("reload_all_datasets")
@injector.inject
def _reload_all_datasets(*args, edm: ErddapDatasetManager = None, **kwargs):
    """Reload all datasets handler"""
    edm.reload_all_datasets(*args, **kwargs)
    return True


def clear_erddap_cache(dataset_id: str = None, _broadcast: int = 1):
    """Clear ERDDAP cache wrapper"""
    return cg.remote_command('clear_erddap_cache', dataset_id=dataset_id or "", _broadcast=_broadcast)


@cg.route("clear_erddap_cache")
@injector.inject
def _clear_erddap_cache(*args, edm: ErddapDatasetManager = None, **kwargs):
    """Clear ERDDAP cache handler"""
    edm.clear_erddap_cache(*args, **kwargs)
    return True


def block_email(email_address, flush: bool = False, _broadcast: int = 1):
    """Block email wrapper"""
    return cg.remote_command("manage_email_block_list", email_address=email_address, block=True, flush=flush, _broadcast=_broadcast)


def unblock_email(email_address, flush: bool = False, _broadcast: int = 1):
    """Unblock email wrapper"""
    return cg.remote_command("manage_email_block_list", email_address=email_address, block=False, flush=flush, _broadcast=_broadcast)


@cg.route("manage_email_block_list")
@injector.inject
def _manage_email_block_list(*args, edm: ErddapDatasetManager = None, **kwargs):
    """Block and unblock email handler"""
    edm.update_email_block_list(*args, **kwargs)
    return True


def block_ip(ip_address, flush: bool = False, _broadcast: int = 1):
    """Block IP address wrapper"""
    return cg.remote_command("manage_ip_block_list", ip_address=ip_address, block=True, flush=flush, _broadcast=_broadcast)


def unblock_ip(ip_address, flush: bool = False, _broadcast: int = 1):
    """Unblock IP address wrapper"""
    return cg.remote_command("manage_ip_block_list", ip_address=ip_address, block=False, flush=flush, _broadcast=_broadcast)


@cg.route("manage_ip_block_list")
@injector.inject
def _manage_ip_block_list(*args, edm: ErddapDatasetManager = None, **kwargs):
    """Block and unblock IP address handler"""
    edm.update_ip_block_list(*args, **kwargs)
    return True


def allow_unlimited(ip_address, flush: bool = False, _broadcast: int = 1):
    """Allow unlimited wrapper"""
    return cg.remote_command("manage_unlimited_allow_list", ip_address=ip_address, allow=True, flush=flush, _broadcast=_broadcast)


def unallow_unlimited(ip_address, flush: bool = False, _broadcast: int = 1):
    """Remove unlimited wrapper"""
    return cg.remote_command("manage_unlimited_allow_list", ip_address=ip_address, allow=False, flush=flush, _broadcast=_broadcast)


@cg.route("manage_unlimited_allow_list")
@injector.inject
def _manage_unlimited_allow_list(*args, edm: ErddapDatasetManager = None, **kwargs):
    """Allow and remove unlimited handler"""
    edm.update_allow_unlimited_list(*args, **kwargs)
    return True


def compile_datasets(skip_errored_datasets: bool = None, reload_all_datasets: bool = False, flush: bool = False, _broadcast: int = 1):
    """Compile datasets wrapper"""
    return cg.remote_command(
        "compile_datasets",
        skip_errored_datasets=skip_errored_datasets,
        reload_all_datasets=reload_all_datasets,
        immediate=flush,
        _broadcast=_broadcast
    )


@cg.route("compile_datasets")
@injector.inject
def _compile_datasets(*args, edm: ErddapDatasetManager = None, **kwargs):
    """Compile datasets handler"""
    edm.compile_datasets(*args, **kwargs)
    return True


@cg.on_tidy
@injector.inject
def _do_tidy(edm: ErddapDatasetManager = None):
    """Tidy up the datasets (e.g. do flushing and such)"""
    edm.flush(False)


@cg.on_shutdown
@injector.inject
def _do_shutdown(edm: ErddapDatasetManager = None):
    """Cleanup the datasets by ensuring flushing has happened"""
    edm.flush(True)
