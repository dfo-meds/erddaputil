import click
import pathlib
from autoinject import injector
import yaml

from erddap_util.sync import SyncDatabase

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
@click.argument("source_path")
@click.argument("target_path")
@click.argument("dataset_id")
@click.option("--recrawl")
@injector.inject
def add_sync_map(source_path, target_path, dataset_id, recrawl, sdb: SyncDatabase):
    # TODO: validate type of recrawl
    sdb.add_sync_mapping(source_path, target_path, recrawl, dataset_id)


@cli.command
@click.argument("map_file")
@injector.inject
def load_sync_map(map_file, sdb: SyncDatabase = None):
    # TODO: validate map_file is a file
    sdb.sync_maps_from_file(map_file)


@cli.command
@injector.inject
def check_sync_maps(sdb: SyncDatabase):
    sdb.enqueue_sync_times()


@cli.command
@click.argument("source_path")
@click.argument("target_path")
@injector.inject
def remove_sync_map(source_path, target_path, sdb: SyncDatabase):
    if sdb.remove_sync_mapping(source_path, target_path):
        print("Sync mapping removed, cleanup of old files scheduled")
    else:
        print("No matching sync mapping found")


@cli.command
@click.argument("source_file")
@injector.inject
def sync(source_file, sdb: SyncDatabase):
    # TODO: Add force option
    if sdb.sync_from_source(source_file):
        print("Sync started")
    else:
        print("No matching source found")


@cli.command
def clean_logs():
    from .logman import ErddapLogManager
    from .daemon import ErddapManagementDaemon
    ErddapManagementDaemon.run_once(ErddapLogManager)


@cli.command
@click.option("--logman/--no-logman", default=False, is_flag=True, type=bool, show_default=True, help="Enable the log cleanup utility")
@click.option("--logtail/--no-logtail", default=False, is_flag=True, type=bool, show_default=True, help="Enable the log tailing utility")
def daemon(logman: bool, logtail: bool):
    daemons = {}
    if logman:
        daemons["logman"] = "erddap_util.logman.ErddapLogManager"
    if logtail:
        daemons["logtail"] = "erddap_util.logtail.ErddapLogTail"
    from .daemon import ErddapManagementDaemon
    daemon = ErddapManagementDaemon(daemons)
    daemon.start()
