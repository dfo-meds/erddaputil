import click
import pathlib
from autoinject import injector

ROOT_DIR = pathlib.Path(__file__).absolute().parent


@click.group
def cli():
    from .common import init_util
    init_util([".erddaputil.cli.yaml", ".erddaputil.cli.toml"])


@cli.command
def clean_logs():
    from .logman import ErddapLogManager
    from .daemon import ErddapManagementDaemon
    ErddapManagementDaemon.run_once(ErddapLogManager)


@cli.command
@click.option("--with-logman", default=False, is_flag=True, type=bool, show_default=True, help="Enable the log management utility")
def daemon(with_logman: bool):
    daemons = {}
    if with_logman:
        from .logman import ErddapLogManager
        daemons["logman"] = ErddapLogManager
    if not daemons:
        print("No daemons specified, exiting")
        exit(0)
    from .daemon import ErddapManagementDaemon
    daemon = ErddapManagementDaemon(daemons)
    daemon.start()
