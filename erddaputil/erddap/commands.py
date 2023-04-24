from erddaputil.main import CommandGroup
from autoinject import injector
from .datasets import ErddapDatasetManager

cg = CommandGroup()


def reload_dataset(dataset_id: str, flag: int = 0, flush: bool = False, _broadcast: bool = True):
    return cg.remote_command("reload_datasets", dataset_id=dataset_id, flag=flag, flush=flush, _broadcast=_broadcast)


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
