import click
import pathlib
from autoinject import injector

ROOT_DIR = pathlib.Path(__file__).absolute().parent


@click.group
def cli():
    from .common import init_util
    init_util([".erddaputil.cli.yaml", ".erddaputil.cli.toml"])


@cli.command
def datasets_reload():
    from .datasets import ErddapDatasetManager


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
