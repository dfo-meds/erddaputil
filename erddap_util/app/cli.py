import click
import pathlib
from autoinject import injector

from erddap_util.util.datasets import ErddapDatasetManager

ROOT_DIR = pathlib.Path(__file__).absolute().parent


@click.group
def cli():
    from erddap_util.util.common import init_util
    init_util([".erddaputil.cli.yaml", ".erddaputil.cli.toml"])


@cli.command
@click.option("--soft", "flag", flag_value=0, default=True)
@click.option("--bad-files", "flag", flag_value=1)
@click.option("--hard", "flag", flag_value=2)
@click.argument("dataset_id")
def reload_dataset(dataset_id: str, flag: int):
    edm = ErddapDatasetManager()
    edm.reload_dataset(dataset_id, flag)


@cli.command
def compile_datasets():
    edm = ErddapDatasetManager()
    edm.compile_datasets()
    edm.metrics.halt()


@cli.command
@click.argument("dataset_id")
def activate_dataset(dataset_id: str):
    edm = ErddapDatasetManager()
    edm.set_active_flag(dataset_id, True)
    edm.metrics.halt()


@cli.command
@click.argument("dataset_id")
def deactivate_dataset(dataset_id: str):
    edm = ErddapDatasetManager()
    edm.set_active_flag(dataset_id, False)
    edm.metrics.halt()


@cli.command
def clean_logs():
    from erddap_util.daemons import ErddapLogManager, ErddapManagementDaemon
    ErddapManagementDaemon.run_once(ErddapLogManager)


@cli.command
@click.option("--logman/--no-logman", default=False, is_flag=True, type=bool, show_default=True, help="Enable the log cleanup utility")
@click.option("--logtail/--no-logtail", default=False, is_flag=True, type=bool, show_default=True, help="Enable the log tailing utility")
def daemon(logman: bool, logtail: bool):
    daemons = {}
    if logman:
        daemons["logman"] = "erddap_util.daemons.logman.ErddapLogManager"
    if logtail:
        daemons["logtail"] = "erddap_util.daemons.logtail.ErddapLogTail"
    from erddap_util.daemons import ErddapManagementDaemon
    daemon = ErddapManagementDaemon(daemons)
    daemon.run_forever()
