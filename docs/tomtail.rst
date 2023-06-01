Tomcat Log Parsing
------------------

ERDDAPUtil supports parsing the Tomcat access logs to identify requests to ERDDAP
and provide both Prometheus statistics and optionally an output of the parsed results.

To enable this feature, ERDDAPUtil must be able to see your Tomcat access logs and have
read access to them. The log directory must also be configured in :confval:`erddaputil.tomtail.log_directory`.

The default settings assume the use of the ``common`` logging format and standard
log prefix (``access_log``), suffix (empty), and encoding (``utf-8``). If you have modified
any of these, you must configure the ``tomtail`` parser accordingly.

If desired, the access logs can be cleaned up by :doc:`/log_management` by setting
:confval:`erddaputil.logman.include_tomcat` to ``true``.

By default, only Prometheus metrics are generated, but output logging of all requests can
be turned on as well. The output log generated has additional information gathered by
parsing the URI for the ERDDAP dataset ID and the DAP parameters in query strings.

Prometheus Metrics
^^^^^^^^^^^^^^^^^^
All metrics have a ``request_type`` (set to ``web``, ``data``, or ``metadata``) and a ``dataset``
(set to the dataset ID or ``-``) label. If your Tomcat logs include a status output (i.e. ``%s``),
then the ``status`` label is also included with the status code.

.. csv-table:: "Prometheus Metrics"
   :header: "Metric Name", "Type", "Description"

   erddap_tomcat_requests,Counter,"Tomcat requests"
   erddap_tomcat_request_bytes,Summary,"Size of tomcat requests in bytes"
   erddap_tomcat_request_processing_time,Summary,"Time to process the request in seconds"

Output Files
^^^^^^^^^^^^
By setting :confval:`erddaputil.tomtail.output_directory`, all requests parsed from Tomcat logs will
be written to a file in the given directory. :confval:`erddaputil.tomtail.output_file_pattern` controls
the file name that will be written to; log files are rotated when the file pattern changes. ``strftime``
is used to format the file name. By default, output files are cleaned up by ``logman``.

The format is controlled by :confval:`erddaputil.tomtail.output_pattern` which includes a subset of
Tomcat variables along with placeholders specific to ERDDAP such as the dataset_id and request_type.

Of note, ERDDAPUtil can parse the DAP parameters for data requests to identify the variables requested
(i.e. the ``projection`` in DAP parlance, output as ``%(dap_variables)s``) and the criteria applied (output
in ``%(dap_constraints)s``. While ERDDAP includes the grid dimensions requested in the projection usually,
ERDDAPUtil separates it into its own ``%(dap_grid_bounds)s`` output since it is repeated on all variables
for a valid ERDDAP request.
