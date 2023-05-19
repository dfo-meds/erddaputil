Configuration
=============
Configuration is done via a TOML file located at ``.erddaputil.toml`` (using the above Docker
configuration). Use the ``.erddaputil.example.toml`` file to create this. Common settings are below,
use the typical TOML format for nested keys to specify them, e.g.:

.. code-block:: toml

   [erddaputil]
   secret_key = "foo"

   [erddaputil.erddap]
   big_parent_directory = "/erddap_data"

Environment variables can also be used by replacing all periods with underscores in the keys below. This
does not work for configuration options that are lists at the moment, such as the peppers.

ERDDAPUtil Core
---------------

.. confval:: erddaputil.compile_on_boot
   :type: bool
   :default: ``true``
   :required: False

   By default, ERDDAPUtil will attempt to compile the ``datasets.xml`` file on boot. Set this to ``false`` to prevent this
   behaviour.

.. confval:: erddaputil.create_default_user_on_boot
   :type: bool
   :default: ``true``
   :required: False

   By default, ERDDAPUtil will attempt to create a user using :confval:`erddaputil.default_username` and
   :confval:`erddaputil.default_password` on boot or reset the password of that user if it already exists.
   Set this to ``false`` to prevent this behaviour.

.. confval:: erddaputil.default_username
   :type: str
   :default: ``admin``
   :required: False

   The username to create on boot, if :confval:`erddaputil.create_default_user_on_boot` is set.

.. confval:: erddaputil.default_password
   :type: str
   :default: ``admin``
   :required: False

   The password to set for the user created on boot, if :confval:`erddaputil.create_default_user_on_boot` is set.

.. confval:: erddaputil.fix_erddap_bpd_permissions
   :type: bool
   :default: ``true``
   :required: False

   ERDDAP's BPD requires the Tomcat user have access to create and manage the directories within it. When a Docker
   volume is used, the permissions are not typically correct. Therefore, ERDDAPUtil attempts to correct this on boot
   to ensure that ERDDAP is useable by running :external+python:func:`os.chown` on it (Linux only). Set this to ``false`` to prevent this
   behaviour. The Tomcat user ID and group ID can be specified via :confval:`erddaputil.erddap.tomcat_uid` and
   :confval:`erddaputil.erddap.tomcat_gid`.

.. confval:: erddaputil.metrics_manager
   :type: str
   :required: False

   Leave this blank to not use the metrics backend or specify a class that has the methods ``send_message(metric: _Metric)``,
   ``start()``, ``terminate()``, and ``join()``. The first will be called every time a metric needs to be updated,
   ``start()`` is used when the metrics are first loaded, and ``terminate()`` and ``join()`` are called in that
   sequence when shutting down. Since the metrics manager is typically a separate thread, ``terminate()`` should
   instruct the thread to gracefully exit and ``start()`` and ``join()`` should be inherited from :external+python:class:`threading.Thread`.

   ERDDAPUtil provides :class:`erddaputil.main.metrics.LocalPrometheusSendThread` which uses the HTTP API's Prometheus
   metrics.

.. confval:: erddaputil.secret_key
   :type: str
   :required: True

   This should be a secret that is the same between all servers that will share an AMPQ exchange or daemon
   and is used to validate that the messages passed are not malicious. It should have at least 192 bits of
   randomness.

.. confval:: erddaputil.show_config
   :type: bool
   :default: ``false``
   :required: False

   Set to ``true`` to dump the configuration to stdout on boot. This is useful for debugging.

.. confval:: erddaputil.use_ampq_exchange
   :type: bool
   :default: ``false``
   :required: False

   Set this to ``true`` to use the AMPQ features.

.. confval:: erddaputil.use_local_daemon
   :type: bool
   :default: ``true``
   :required: False

   Set this to ``false`` if you want to only send messages to AMPQ from the CLI or HTTP API.


ERDDAP Configuration
--------------------
.. confval:: erddaputil.erddap.base_url
   :type: str
   :required: False

   The base URL for ERDDAP (e.g. ``http://localhost:8080/erddap``). Note that, unlike ERDDAP, this
   should include the ``/erddap`` path.

.. confval:: erddaputil.erddap.big_parent_directory
   :type: path
   :required: False

   Set to the same value as ERDDAP's ``bigParentDirectory`` configuration value

.. confval:: erddaputil.erddap.datasets_d
   :type: path
   :required: False

   Set to the directory containing XML files with dataset definitions in them. These should be
   identical to the ones created for ERDDAP, but each in their own XML file. Each XML file should
   contain exactly one ``<dataset>`` tag as the root-level element. While ERDDAP requires datasets
   use ISO-8859-1 encoding, these datasets can use any encoding as long as it is declared and
   compatible with ISO-8859-1 (illegal characters will be replaced).

.. confval:: erddaputil.erddap.datasets_xml_template
   :type: path
   :required: False

   By default, ERDDAPUtil will use an empty ``<erddapDatasets>`` tag to generate ``datasets.xml``.
   If you want to supply your own template, provide it here. ERDDAPUtil will only modify it by
   (a) adding all of the datasets found in ``datasets.d`` and (b) updating the block and allow lists.
   Your template file may use a different character encoding as long as it is ISO-8859-1 compatible.

.. confval:: erddaputil.erddap.ip_block_list
   :type: path
   :required: False

   A path to a text file of IP addresses, ranges, or subnets to block requests from (one entry per
   line). Defaults to ``{BIG_PARENT_DIRECTORY}/.ip_block_list.txt``

.. confval:: erddaputil.erddap.subscription_block_list
   :type: path
   :required: False

   A path to a text file of emails to block subscriptions for (one email per line). Defaults to
   ``{BIG_PARENT_DIRECTORY}/.email_block_list.txt``

.. confval:: erddaputil.erddap.tomcat_gid
   :type: int
   :default: ``1000``
   :required: False

   The group ID that tomcat runs as. This is used only if ``erddaputil.fix_erddap_bpd_permissions`` is
   set to ``true``.

.. confval:: erddaputil.erddap.tomcat_uid
   :type: int
   :default: ``1000``
   :required: False

   The user ID that tomcat runs as. This is used only if ``erddaputil.fix_erddap_bpd_permissions`` is
   set to ``true``.

.. confval:: erddaputil.erddap.unlimited_allow_list
   :type: path
   :required: False

   A path to a text file of IP addresses, ranges, or subnets to allow unlimited access to (one entry
   per line). Defaults to ``{BIG_PARENT_DIRECTORY}/.unlimited_allow_list.txt``

Dataset Management
------------------
.. confval:: erddaputil.dataset_manager.backups
   :type: path
   :required: False

   If specified, whenever a new ``datasets.xml`` file is generated, the old one will be backed-up
   into this folder. Backups are cleaned up according to the below retention setting.

.. confval:: erddaputil.dataset_manager.backup_retention_days
   :type: int
   :default: ``31``
   :required: False

   Backups of ``datasets.xml`` are deleted after the given number of days.

.. confval:: erddaputil.dataset_manager.max_delay_seconds
   :type: float
   :default: ``0``
   :required: False

   ERDDAPUtil delays briefly before performing a reload of a dataset, in case another similar
   request comes in (e.g. if your automation pipeline is pushing dozens of requests at once).
   This setting allows you to control the longest ERDDAPUtil will wait after the last request
   for a given dataset to be reloaded before it will execute the request. Set to 0 to always
   immediately execute every request for a reload.

.. confval:: erddaputil.dataset_manager.max_pending
   :type: int
   :default: ``0``
   :required: False

   ERDDAPUtil delays briefly before performing a reload of a dataset, in case another similar
   request comes in (e.g. if your automation pipeline is pushing dozens of requests at once).
   This setting allows you to control the maximum number of datasets pending reload; once the
   threshold is exceeded, the oldest request is executed immediately. Set to 0 to ignore the
   threshold.

.. confval:: erddaputil.dataset_manager.max_recompile_delay
   :type: float
   :default: ``0``
   :required: False

   Similar to how dataset reloads are delayed, recompilation can also be delayed for similar
   reasons. ERDDAPUtil will wait until this many seconds have elapsed since the last request
   for recompilation before actually performing the recompilation. Set to 0 to always
   recompile immediately when requested.

.. confval:: erddaputil.dataset_manager.skip_misconfigured_datasets
   :type: bool
   :default: ``true``
   :required: False

   When recompiling datasets, users may instruct ERDDAPUtil to either skip datasets that are
   not well-formed XML, raise an error and fail when such a dataset is found, or use the default
   value. This is the default value; set to ``true`` to skip the datasets (the default) or ``false``
   to raise an error. Note that failed datasets are still logged by ERDDAPUtil so they can be
   remedied; if ``false``, this mostly means that ERDDAPUtil will not update ``datasets.xml`` until the
   file is fixed (the default is to omit it from ``datasets.xml``)

Log Management
--------------
.. confval:: erddaputil.logman.enabled
   :type: bool
   :default: ``true``
   :required: False

   Set to ``false`` to disable log management.

.. confval:: erddaputil.logman.file_prefixes
   :type: list
   :default: ``logArchivedAt``, ``logPreviousArchivedAt``, ``emailLog``
   :required: False

   A list of files to remove by prefix. Includes all of ERDDAP's log files by default.

.. confval:: erddaputil.logman.retention_days
   :type: int
   :default: ``31``
   :required: False

   Days to keep ERDDAP log files (i.e. files in ``{BIG_PARENT_DIRECTORY}/logs``) before removing them.

.. confval:: erddaputil.logman.sleep_time_seconds
   :type: float
   :default: ``3600``
   :required: False

   Number of seconds to wait between log clean-up jobs.

AMPQ Integration
----------------
.. confval:: erddaputil.ampq.cluster_name
   :type: str
   :required: False

   If you are using AMPQ, this should be a unique value for each set of ERDDAP machines that
   should all respond to the same commands.

.. confval:: erddaputil.ampq.connection
   :type: str
   :required: False

   Either a string for :external+pika:class:`pika.connection.URLParameters` (for pika integration) or the
   `connection string (for Azure Service Bus) <https://learn.microsoft.com/en-us/python/api/azure-servicebus/azure.servicebus.servicebusclient?view=azure-python#azure-servicebus-servicebusclient-from-connection-string>`_

.. confval:: erddaputil.ampq.create_queue
   :type: bool
   :default: ``true``
   :required: False

   If set to false, prevents ERDDAPUtil from automatically trying to create and bind the queue or
   create the subscription/rules.

.. confval:: erddaputil.ampq.exchange_name
   :type: str
   :default: ``erddap_cnc``
   :required: False

   The RabbitMQ exchange name or the Azure Service Bus topic name.

.. confval:: erddaputil.ampq.hostname
   :type: str
   :required: False

   If you are using AMPQ, this should be a unique value for each machine. Defaults to
   :external+python:func:`socket.gethostname`

.. confval:: erddaputil.ampq.implementation
   :type: str
   :default: ``pika``
   :required: False

   Set to ``pika`` or ``azure_service_bus`` depending which client library to use.

Web API
-------
.. confval:: erddaputil.webapp.enable_management_api
   :type: bool
   :default: ``true``
   :required: False

   Set to ``false`` to disable the management API

.. confval:: erddaputil.webapp.enable_metrics_collector
   :type: bool
   :default: ``true``
   :required: False

   Set to ``false`` to disable the metrics collector (this is like our own pushgateway)

.. confval:: erddaputil.webapp.iterations_jitter
   :type: int
   :default: ``100000``
   :required: False

   ERDDAPUtil uses :external+python:func:`hashlib.pbkdf2_hmac` to hash and store user
   passwords, using a unique salt and number of iterations for each user. The number
   of iterations will be up to this value higher than :confval:`erddaputil.webapp.min_iterations`,
   chosen at random.

.. confval:: erddaputil.webapp.min_iterations
   :type: int
   :default: ``700000``
   :required: False

   ERDDAPUtil uses :external+python:func:`hashlib.pbkdf2_hmac` to hash and store user
   passwords, using a unique salt and number of iterations for each user. The number
   of iterations will be at least this many.

.. confval:: erddaputil.webapp.password_file
   :type: path
   :required: False

   Set to the path of a file where passwords for the web API will be stored.

.. confval:: erddaputil.webapp.password_hash
   :type: str
   :default: ``sha256``
   :required: False

   Set to the name of a hash function supported by :external+python:mod:`hashlib`.

.. confval:: erddaputil.webapp.peppers
   :type: list
   :required: True

   Set to a list of random strings that are hard to guess. The first one will be used to
   create new passwords and they will all be tried when validating a user's password.

.. confval:: erddaputil.webapp.salt_length
   :type: int
   :default: ``16``
   :required: False

   The length of the salt for new passwords (in bytes). Salts are generated using
   :external+python:func:`secrets.token_urlsafe`

Metrics Manager - LocalPrometheus
---------------------------------
.. confval:: erddaputil.localprom.host
   :type: str
   :default: ``localhost``
   :required: False

   The host to push statistics to.

.. confval:: erddaputil.localprom.port
   :type: int
   :default: ``7193``
   :required: False

   The port to push statistics to

.. confval:: erddaputil.localprom.username
   :type: str
   :required: False

   The username to login to the web API with.

.. confval:: erddaputil.localprom.password
   :type: str
   :required: False

   The password to login to the web API with.

.. confval:: erddaputil.localprom.batch_size
   :type: int
   :default: ``200``
   :required: False

   The maximum number of metric updates to send it one batch to the web API.

.. confval:: erddaputil.localprom.batch_wait_seconds
   :type: float
   :default: ``2``
   :required: False

   The maximum amount of time to delay sending metrics while waiting for a whole batch.

.. confval:: erddaputil.localprom.max_retries
   :type: int
   :default: ``3``
   :required: False

   The maximum number of times to retry sending a batch to the web API before discarding them. Set
   to ``-1`` to retry forever or ``0`` to only try once. When the daemon is being shutdown, this is overridden
   to not retry at all.

.. confval:: erddaputil.localprom.max_tasks
   :type: int
   :default: ``5``
   :required: False

   The maximum number of batches that will be handled at the same time (defaults to 5). Metrics
   wait in a queue while not being handled.

.. confval:: erddaputil.localprom.retry_delay_seconds
   :type: float
   :default: ``2``
   :required: False

   The delay between retries to send metrics.

Status Scraper
--------------

.. confval:: erddaputil.status_scraper.enabled
   :type: bool
   :default: ``true``
   :required: False

   Set to ``false`` to disable the scraping of ``status.html``.

.. confval:: erddaputil.status_scraper.memory_path
   :type: path
   :required: False

   Set the path of a file where information about the last scrape of status.html
   is stored. Defaults to a location under ERDDAP's ``bigParentDirectory`` if set,
   otherwise you must provide one.

.. confval:: erddaputil.status_scraper.sleep_time_seconds
   :type: float
   :default: ``300``
   :required: False

   The time to wait between scrapes.

.. confval:: erddaputil.status_scraper.start_delay_seconds
   :type: float
   :default: ``180.0``
   :required: False

   The time to wait after startup before starting to scrape to give ERDDAP time to
   boot.

Daemon Service
--------------
.. confval:: erddaputil.daemon.host
   :type: str
   :default: ``127.0.0.1``
   :required: False

   The host the ERDDAP HTTP, CLI, and AMPQ APIs will send messages to.

.. confval:: erddaputil.daemon.port
   :type: int
   :default: ``9172``
   :required: False

   The port the ERDDAP HTTP, CLI, and AMPQ APIs will send messages to.

.. confval:: erddaputil.service.host
   :type: str
   :default: ``127.0.0.1``
   :required: False

   The IP address the ERDDAPUtil service will listen to.

.. confval:: erddaputil.service.port
   :type: int
   :default: ``9172``
   :required: False

   The port the ERDDAPUtil service will listen on.

.. confval:: erddaputil.service.backlog
   :type: int
   :default: ``20``
   :required: False

   The backlog of TCP connections that the daemon server will hold.

.. confval:: erddaputil.service.listen_block_seconds
   :type: float
   :default: ``0.25``
   :required: False

   The time to block while waiting for a new connection. Tidying jobs will be run approximately this
   often.
