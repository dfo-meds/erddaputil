import logging

try:
    from erddap_util.app.app import create_app
    app = create_app()
    app.cli()
except Exception as ex:
    logging.getLogger("erddap_util").exception(ex)
    exit(1)
