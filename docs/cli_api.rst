CLI Documentation
=================

Commands can be called from the command line as follows:

.. code-block:: Shell

   # Directly
   python -m erddaputil COMMAND_NAME [OPTIONS] [ARGUMENTS]

   # Within Docker Container
   docker exec erddaputil_daemon python -m erddaputil COMMAND_NAME [OPTIONS] [ARGUMENTS]


.. csv-table:: ERDDAPUtil Commands
   :header: "Command", "Description"

   ``reload-dataset [-b] [-h] [-i] [-L] [-G] DATASET_ID``,Places a flag file for ERDDAP to reload the dataset ASAP. Specify ``-b`` for a "bad files" reload OR ``-h`` for a hard reload. See also :doc:`/dataset_manager`.
   ``reload-all-datasets [-b] [-h] [-i] [-L] [-G]``,Places a flag file for ERDDAP to reload every dataset defined in ``datasets.xml``. Takes the same arguments as ``reload-dataset`` except ``DATASET_ID``. See also :doc:`/dataset_manager`.
   ``compile-datasets [-i] [-L] [-G]``,Recompile the datasets from the config directory (see below) and reloads any modified datasets. See also :doc:`/dataset_manager`.
   ``activate-dataset [-i] [-L] [-G] DATASET_ID``,Sets the ``active=True`` attribute on the dataset in the config directory (see below) then recompiles the datasets. See also :doc:`/dataset_manager`.
   ``deactivate-dataset [-i] [-L] [-G] DATASET_ID``,As above but sets ``active=False``. See also :doc:`/dataset_manager`.
   ``block-email [-i] [-L] [-G] EMAIL``,Adds an email to the subscription block list then recompiles the datasets. See also :doc:`/control_lists`.
   ``block-ip [-i] [-L] [-G] IP_ADDRESS``,Adds an IP to the block list then recompiles the datasets. See also :doc:`/control_lists`.
   ``allow-unlimited [-i] [-L] [-G] IP_ADDRESS``,Adds an IP to the unlimited allow list then recompiles the datasets. See also :doc:`/control_lists`.
   ``unblock-email [-i] [-L] [-G] EMAIL``,Remove an email from the subscription block list then recompiles the datasets. See also :doc:`/control_lists`.
   ``unblock-ip [-i] [-L] [-G] IP_ADDRESS``,Remove an IP from the block list then recompiles the datasets. See also :doc:`/control_lists`.
   ``remove-unlimited [-i] [-L] [-G] IP_ADDRESS``,Remove an IP from the unlimited allow list then recompiles the datasets. See also :doc:`/control_lists`.
   ``flush-logs [-L] [-G]``,Forces ERDDAP to flush logs to ``log.txt`` immediately by requesting the status.html page. See also :doc:`/dataset_manager`.
   ``list-datasets``,Lists the datasets available in this ERDDAP. Only works if there is a local ERDDAP server connected to the ERDDAPUtil. See also :doc:`/dataset_manager`.
   ``clear-cache [-L] [-G] [DATASET_ID]``,Removes all of the files within the ``decompressed`` directory. If ``DATASET_ID`` is specified then only the given dataset is removed. See also :doc:`/dataset_manager`.

General Options and Arguments
-----------------------------

| ``-b``
| ``-h``

    When reloading a dataset, these options specify a "bad files" or a "hard" reload as per the ERDDAP documentation.

``-i``
    Ignores any configured delay on reloading or recompiling. Note that if other dataset reloads are pending, they will
    be performed immediately as well.

``-L``
    Prevent broadcasting the command on AMPQ. See :doc:`/ampq_api`.

``-G``
    Broadcast on the global AMPQ topic instead of the cluster AMPQ topic. See :doc:`/ampq_api`.

``DATASET_ID``
    A single dataset ID (as specified in the XML file) or a comma-delimited list of them

``IP_ADDRESS``
    A single IP address, a subnet mask (e.g. ``10.0.0.0/24``), an IP range supported by ERDDAP (e.g. ``10.0.*.*`` or
    ``10.0.0.*``), or multiple such entries separated by commas.

``EMAIL``
    An email address or a comma-delimited list of email addresses. Note that ERDDAP does not allow commas in email
    addresses.
