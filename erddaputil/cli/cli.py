"""Command line tools for ERDDAP management."""
import click
from erddaputil.webapp.common import AuthChecker
from erddaputil.common import init_config
from autoinject import injector
import functools
import logging


@click.group("base")
def base():
    """All command groups"""
    init_config()


def handle_command_response(fn: callable):
    """Turns a CommandResponse object into output for the user."""

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
@click.argument("dataset_id", default="")
@click.option("--soft", "-s", "flag", flag_value=0, default=True, help="Scan for new files and update the information from the datasets file.")
@click.option("--bad-files", "-b", "flag", flag_value=1, help="Remove and reload all bad files in addition to scanning and updating the information.")
@click.option("--hard", "-h", "flag", flag_value=2, help="Remove the entire dataset (except the decompression cache) and rebuild it from scratch.")
@click.option("--delay/--no-delay", "-d/-i", default=True, help="Whether to delay the action (using configured delays) or immediately push the change.")
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True, help="Whether to broadcast this command via AMPQ to all servers in the cluster (if configured)")
@handle_command_response
def reload_dataset(dataset_id: str = "", flag: int = 0, delay: bool = True, broadcast: bool = True):
    """Reload a dataset"""
    if not dataset_id:
        from erddaputil.erddap.commands import reload_all_datasets
        return reload_all_datasets(flag, flush=not delay, _broadcast=broadcast)
    else:
        from erddaputil.erddap.commands import reload_dataset
        return reload_dataset(dataset_id, flag, flush=not delay, _broadcast=broadcast)

@base.command
@click.argument("dataset_id")
@click.option("--delay/--no-delay", "-d/-i", default=True, help="Whether to delay the action (using configured delays) or immediately push the change.")
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True, help="Whether to broadcast this command via AMPQ to all servers in the cluster (if configured)")
@handle_command_response
def activate_dataset(dataset_id: str, delay: bool = True, broadcast: bool = True):
    """Activate a dataset"""
    from erddaputil.erddap.commands import activate_dataset
    return activate_dataset(dataset_id, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("dataset_id")
@click.option("--delay/--no-delay", "-d/-i", default=True, help="Whether to delay the action (using configured delays) or immediately push the change.")
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True, help="Whether to broadcast this command via AMPQ to all servers in the cluster (if configured)")
@handle_command_response
def deactivate_dataset(dataset_id: str, delay: bool = True, broadcast: bool = True):
    """Deactivate a dataset"""
    from erddaputil.erddap.commands import deactivate_dataset
    return deactivate_dataset(dataset_id, flush=not delay, _broadcast=broadcast)


@base.command
@click.option("--skip/--fail", "-s/-f", default=True, help="Whether to skip (skip) or raise an error (fail) when a dataset's XML is invalid")
@click.option("--reload-all", "-r", is_flag=True, default=False, help="Perform a soft reload on all datasets")
@click.option("--delay/--no-delay", "-d/-i", default=True, help="Whether to delay the action (using configured delays) or immediately push the change.")
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True, help="Whether to broadcast this command via AMPQ to all servers in the cluster (if configured)")
@handle_command_response
def compile_datasets(skip: bool = True, reload_all: bool = False, delay: bool = True, broadcast: bool = True):
    """Compile datasets from a directory of datasets"""
    from erddaputil.erddap.commands import compile_datasets
    return compile_datasets(skip, reload_all, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("email")
@click.option("--delay/--no-delay", "-d/-i", default=True, help="Whether to delay the action (using configured delays) or immediately push the change.")
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True, help="Whether to broadcast this command via AMPQ to all servers in the cluster (if configured)")
@handle_command_response
def block_email(email: str, delay: bool = True, broadcast: bool = True):
    """Block subscription access to an email"""
    from erddaputil.erddap.commands import block_email
    return block_email(email, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("ip")
@click.option("--delay/--no-delay", "-d/-i", default=True, help="Whether to delay the action (using configured delays) or immediately push the change.")
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True, help="Whether to broadcast this command via AMPQ to all servers in the cluster (if configured)")
@handle_command_response
def block_ip(ip: str, delay: bool = True, broadcast: bool = True):
    """Block all requests from an IP address"""
    from erddaputil.erddap.commands import block_ip
    return block_ip(ip, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("ip")
@click.option("--delay/--no-delay", "-d/-i", default=True, help="Whether to delay the action (using configured delays) or immediately push the change.")
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True, help="Whether to broadcast this command via AMPQ to all servers in the cluster (if configured)")
@handle_command_response
def allow_unlimited(ip: str, delay: bool = True, broadcast: bool = True):
    """Allow unlimited access by an IP address"""
    from erddaputil.erddap.commands import allow_unlimited
    return allow_unlimited(ip, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("email")
@click.option("--delay/--no-delay", "-d/-i", default=True, help="Whether to delay the action (using configured delays) or immediately push the change.")
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True, help="Whether to broadcast this command via AMPQ to all servers in the cluster (if configured)")
@handle_command_response
def unblock_email(email: str, delay: bool = True, broadcast: bool = True):
    """Block subscription access to an email"""
    from erddaputil.erddap.commands import unblock_email
    return unblock_email(email, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("ip")
@click.option("--delay/--no-delay", "-d/-i", default=True, help="Whether to delay the action (using configured delays) or immediately push the change.")
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True, help="Whether to broadcast this command via AMPQ to all servers in the cluster (if configured)")
@handle_command_response
def unblock_ip(ip: str, delay: bool = True, broadcast: bool = True):
    """Block all requests from an IP address"""
    from erddaputil.erddap.commands import unblock_ip
    return unblock_ip(ip, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("ip")
@click.option("--delay/--no-delay", "-d/-i", default=True, help="Whether to delay the action (using configured delays) or immediately push the change.")
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True, help="Whether to broadcast this command via AMPQ to all servers in the cluster (if configured)")
@handle_command_response
def remove_unlimited(ip: str, delay: bool = True, broadcast: bool = True):
    """Allow unlimited access by an IP address"""
    from erddaputil.erddap.commands import unallow_unlimited
    return unallow_unlimited(ip, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("username")
@click.password_option(help="The password for the user.")
@injector.inject
def set_password(username: str, password: str, ac: AuthChecker = None):
    """Set the password for a user's access to a web API"""
    ac.set_credentials(username, password)
    print(f"Credentials set for {username}")


@base.command
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True, help="Whether to broadcast this command via AMPQ to all servers in the cluster (if configured)")
def flush_logs(broadcast: bool = True):
    """Flush the ERDDAP logs to disk."""
    from erddaputil.erddap.commands import flush_logs
    return flush_logs(broadcast)


@base.command
def list_datasets():
    """List the datasets currently available in ERDDAP"""
    from erddaputil.erddap.commands import list_datasets
    return list_datasets()


@base.command
@click.argument("dataset_id", default="")
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True, help="Whether to broadcast this command via AMPQ to all servers in the cluster (if configured)")
def clear_cache(dataset_id: str, broadcast: bool = True):
    """Clear the decompressed folder for ERDDAP."""
    from erddaputil.erddap.commands import clear_erddap_cache
    return clear_erddap_cache(dataset_id, broadcast)
