import click
import pathlib
from autoinject import injector

ROOT_DIR = pathlib.Path(__file__).absolute().parent


@click.group
def cli():
    from .common import init_util
    init_util([".erddaputil.cli.yaml", ".erddaputil.cli.toml"])


@cli.command
@click.option("--soft", "flag", flag_value=0, default=True)
@click.option("--bad-files", "flag", flag_value=1)
@click.option("--hard", "flag", flag_value=2)
@click.argument("dataset_id")
def reload_dataset(dataset_id: str, flag: int):
    from .datasets import ErddapDatasetManager
    edm = ErddapDatasetManager()
    edm.reload_dataset(dataset_id, flag)


@cli.command
def compile_datasets():
    from .datasets import ErddapDatasetManager
    edm = ErddapDatasetManager()
    edm.compile_datasets()
    edm.metrics.halt()


@cli.command
@click.argument("dataset_id")
def activate_dataset(dataset_id: str):
    from .datasets import ErddapDatasetManager
    edm = ErddapDatasetManager()
    edm.set_active_flag(dataset_id, True)
    edm.metrics.halt()

@cli.command
@click.argument("dataset_id")
def deactivate_dataset(dataset_id: str):
    from .datasets import ErddapDatasetManager
    edm = ErddapDatasetManager()
    edm.set_active_flag(dataset_id, False)
    edm.metrics.halt()

@cli.command
def clean_logs():
    from .logman import ErddapLogManager
    from .daemon import ErddapManagementDaemon
    ErddapManagementDaemon.run_once(ErddapLogManager)


@cli.command
@click.option("--logman/--no-logman", default=False, is_flag=True, type=bool, show_default=True, help="Enable the log cleanup utility")
@click.option("--logtail/--no-logtail", default=False, is_flag=True, type=bool, show_default=True, help="Enable the log tailing utility")
def daemon(with_logman: bool, with_logtail: bool):
    daemons = {}
    if with_logman:
        daemons["logman"] = "erddap_util.logman.ErddapLogManager"
    if with_logtail:
        daemons["logtail"] = "erddap_util.logtail.ErddapLogTail"
    from .daemon import ErddapManagementDaemon
    daemon = ErddapManagementDaemon(daemons)
    daemon.start()
