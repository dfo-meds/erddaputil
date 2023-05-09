import click
from erddaputil.webapp.common import AuthChecker
from erddaputil.common import init_config
from autoinject import injector
import functools
import logging


@click.group("base")
def base():
    init_config()


def error_shield(fn):

    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            resp = fn(*args, **kwargs)
            if resp.state == "success":
                print(f"Result: success")
                print(resp.message)
            else:
                print(f"Result: failed")
                print(resp.message)
        except Exception as ex:
            logging.getLogger().exception(ex)

    return wrapped


@base.command
@click.argument("dataset_id")
@click.option("--soft", "-s", "flag", flag_value=0, default=True)
@click.option("--bad-files", "-b", "flag", flag_value=1)
@click.option("--hard", "-h", "flag", flag_value=2)
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def reload_dataset(dataset_id, flag, delay, broadcast):
    """Reload a dataset"""
    from erddaputil.erddap.commands import reload_dataset
    return reload_dataset(dataset_id, flag, flush=not delay, _broadcast=broadcast)


@base.command
@click.option("--soft", "-s", "flag", flag_value=0, default=True)
@click.option("--bad-files", "-b", "flag", flag_value=1)
@click.option("--hard", "-h", "flag", flag_value=2)
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def reload_all_datasets(flag, delay, broadcast):
    """Reload all datasets"""
    from erddaputil.erddap.commands import reload_all_datasets
    return reload_all_datasets(flag, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("dataset_id")
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def activate_dataset(dataset_id, delay, broadcast):
    """Activate a dataset"""
    from erddaputil.erddap.commands import activate_dataset
    return activate_dataset(dataset_id, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("dataset_id")
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def deactivate_dataset(dataset_id, delay, broadcast):
    """Deactivate a dataset"""
    from erddaputil.erddap.commands import deactivate_dataset
    return deactivate_dataset(dataset_id, flush=not delay, _broadcast=broadcast)


@base.command
@click.option("--skip/--fail", "-s/-f", default=True)
@click.option("--reload-all", "-r", is_flag=True, default=False)
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def compile_datasets(skip, reload_all, delay, broadcast):
    """Compile datasets from a directory of datasets"""
    from erddaputil.erddap.commands import compile_datasets
    return compile_datasets(skip, reload_all, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("email")
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def block_email(email, delay, broadcast):
    """Block subscription access to an email"""
    from erddaputil.erddap.commands import block_email
    return block_email(email, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("ip")
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def block_ip(ip, delay, broadcast):
    """Block all requests from an IP address"""
    from erddaputil.erddap.commands import block_ip
    return block_ip(ip, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("ip")
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def allow_unlimited(ip, delay, broadcast):
    """Allow unlimited access by an IP address"""
    from erddaputil.erddap.commands import allow_unlimited
    return allow_unlimited(ip, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("email")
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def unblock_email(email, delay, broadcast):
    """Block subscription access to an email"""
    from erddaputil.erddap.commands import unblock_email
    return unblock_email(email, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("ip")
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def unblock_ip(ip, delay, broadcast):
    """Block all requests from an IP address"""
    from erddaputil.erddap.commands import unblock_ip
    return unblock_ip(ip, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("ip")
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def remove_unlimited(ip, delay, broadcast):
    """Allow unlimited access by an IP address"""
    from erddaputil.erddap.commands import unallow_unlimited
    return unallow_unlimited(ip, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("username")
@click.password_option()
@injector.inject
def set_password(username, password, ac: AuthChecker = None):
    """Set the password for a user's access to a web API"""
    ac.set_credentials(username, password)
    print(f"Credentials set for {username}")


@base.command
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
def flush_logs(broadcast):
    from erddaputil.erddap.commands import flush_logs
    return flush_logs(broadcast)


@base.command
def list_datasets():
    from erddaputil.erddap.commands import list_datasets
    return list_datasets()


@base.command
@click.argument("dataset_id", default="")
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
def clear_cache(dataset_id, broadcast):
    from erddaputil.erddap.commands import clear_erddap_cache
    return clear_erddap_cache(dataset_id, broadcast)
