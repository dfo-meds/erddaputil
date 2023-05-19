Command Line Interface
======================

Commands can be called from the command line as follows:

.. code-block:: Shell

   # Directly
   python -m erddaputil COMMAND_NAME [OPTIONS] [ARGUMENTS]

   # Within Docker Container
   docker exec erddaputil_daemon python -m erddaputil COMMAND_NAME [OPTIONS] [ARGUMENTS]

.. click:: erddaputil.cli.cli:base
   :prog: python -m erddaputil
   :nested: full


Argument Notes
--------------

``DATASET_ID``
    A single dataset ID (as specified in the XML file) or a comma-delimited list of them

``IP_ADDRESS``
    A single IP address, a subnet mask (e.g. ``10.0.0.0/24``), an IP range supported by ERDDAP (e.g. ``10.0.*.*`` or
    ``10.0.0.*``), or multiple such entries separated by commas.

``EMAIL``
    An email address or a comma-delimited list of email addresses. Note that ERDDAP does not allow commas in email
    addresses.
