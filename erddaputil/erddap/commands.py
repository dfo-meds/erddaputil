from erddaputil.main import CommandGroup
from autoinject import injector
from .datasets import ErddapDatasetManager

cg = CommandGroup()


def reload_dataset(dataset_id: str, flag: int = 0, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("reload_datasets", dataset_id=dataset_id, flag=flag, flush=flush, _broadcast=_broadcast)


def activate_dataset(dataset_id: str, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("set_active_flag", dataset_id=dataset_id, active_flag=True, flush=flush, _broadcast=_broadcast)


def deactivate_dataset(dataset_id: str, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("set_active_flag", dataset_id=dataset_id, active_flag=False, flush=flush, _broadcast=_broadcast)


def reload_all_datasets(flag: int = 0, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("reload_all_datasets", flag=flag, flush=flush, _broadcast=_broadcast)


def block_email(email_address, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("block_email", email_address=email_address, flush=flush, _broadcast=_broadcast)


def block_ip(ip_address, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("block_ip", ip_address=ip_address, flush=flush, _broadcast=_broadcast)


def allow_unlimited(ip_address, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("allow_unlimited", ip_address=ip_address, flush=flush, _broadcast=_broadcast)


def compile_datasets(skip_errored_datasets: bool = None, reload_all_datasets: bool = False, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command(
        "compile_datasets",
        skip_errored_datasets=skip_errored_datasets,
        reload_all_datasets=reload_all_datasets,
        immediate=flush,
        _broadcast=_broadcast
    )


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


@cg.route("block_email")
@injector.inject
def _set_active_flag(*args, edm: ErddapDatasetManager = None, **kwargs):
    edm.block_email(*args, **kwargs)
    return True


@cg.route("block_email")
@injector.inject
def _block_email(*args, edm: ErddapDatasetManager = None, **kwargs):
    edm.block_email(*args, **kwargs)
    return True


@cg.route("block_ip")
@injector.inject
def _block_ip(*args, edm: ErddapDatasetManager = None, **kwargs):
    edm.block_ip(*args, **kwargs)
    return True


@cg.route("allow_unlimited")
@injector.inject
def _allow_unlimited(*args, edm: ErddapDatasetManager = None, **kwargs):
    edm.allow_unlimited(*args, **kwargs)
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
