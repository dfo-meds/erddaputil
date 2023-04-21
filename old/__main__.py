import logging

try:
    from old.app.app import create_app
    app = create_app()
    app.cli()
except Exception as ex:
    logging.getLogger("erddaputil").exception(ex)
    exit(1)
