from .cli import cli
import logging

try:
    cli()
except Exception as ex:
    logging.getLogger("erddap_util").exception(ex)
    exit(1)
