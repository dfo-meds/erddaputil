import click


@click.group("base")
def base():
    pass


@base.command
@click.argument("dataset_id")
def reload_dataset(dataset_id):
    from erddaputil.erddap.commands import reload_dataset
    response = reload_dataset(dataset_id)
    print(response)


