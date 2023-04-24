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
@click.argument("--soft", "-s", "flag", flag_value=0, default=True)
@click.argument("--bad-files", "-b", "flag", flag_value=1)
@click.argument("--hard", "-h", "flag", flag_value=2)
@click.argument("--immediate/--delayed", "-i/-d", default=False)
@click.argument("--broadcast/--no-broadcast", "-C/-L", default=True)
@error_shield
def reload_dataset(dataset_id, flag, immediate, broadcast):
    from erddaputil.erddap.commands import reload_dataset
    return reload_dataset(dataset_id, flag, flush=immediate, _broadcast=broadcast)


