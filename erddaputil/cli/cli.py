import click


@click.group("base")
def base():
    pass


def error_shield(fn):

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
            print(f"An error occurred:")
            print(f"{type(ex)}: {str(ex)}")

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
    from erddaputil.erddap.commands import reload_all_datasets
    return reload_all_datasets(flag, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("dataset_id")
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def activate_dataset(dataset_id, delay, broadcast):
    from erddaputil.erddap.commands import activate_dataset
    return activate_dataset(dataset_id, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("dataset_id")
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def deactivate_dataset(dataset_id, delay, broadcast):
    from erddaputil.erddap.commands import deactivate_dataset
    return deactivate_dataset(dataset_id, flush=not delay, _broadcast=broadcast)


@base.command
@click.option("--skip/--fail", "-s/-f", default=True)
@click.option("--reload-all", "-r", is_flag=True, default=False)
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def compile_datasets(skip, reload_all, delay, broadcast):
    from erddaputil.erddap.commands import compile_datasets
    return compile_datasets(skip, reload_all, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("email")
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def block_email(email, delay, broadcast):
    from erddaputil.erddap.commands import block_email
    return block_email(email, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("ip")
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def block_ip(ip, delay, broadcast):
    from erddaputil.erddap.commands import block_ip
    return block_ip(ip, flush=not delay, _broadcast=broadcast)


@base.command
@click.argument("ip")
@click.option("--delay/--no-delay", "-d/-i", default=True)
@click.option("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def allow_unlimited(ip, delay, broadcast):
    from erddaputil.erddap.commands import allow_unlimited
    return allow_unlimited(ip, flush=not delay, _broadcast=broadcast)