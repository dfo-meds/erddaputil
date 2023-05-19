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
``erddaputil.compile_on_boot``
    By default, ERDDAPUtil will attempt to compile the ``datasets.xml`` file on boot. Set this to ``false`` to prevent this
    behaviour.

``erddaputil.create_default_user_on_boot``
    By default, ERDDAPUtil will attempt to create a user using the default username and password (see below) on boot or
    reset the password of that user if it already exists. Set this to ``false`` to prevent this behaviour.

``erddaputil.default_username``
``erddaputil.default_password``
    The default credentials used for the default user created on boot.

``erddaputil.fix_erddap_bpd_permissions``
    ERDDAP's BPD requires the Tomcat user have access to create and manage the directories within it. When a Docker
    volume is used, the permissions are not typically correct. Therefore, ERDDAPUtil attempts to correct this on boot
    to ensure that ERDDAP is useable by running ``chown`` on it (Linux only). Set this to ``false`` to prevent this
    behaviour. The Tomcat user ID and group ID can be specified via ``erddaputil.erddap.tomcat_uid`` and
    ``erddaputil.erddap.tomcat_gid`` (the default is 1000:1000 as per the Axiom ERDDAP Docker image).

``erddaputil.metrics_manager``
    Leave this blank to not use the metrics backend or specify a class that has the methods ``send_message(metric: _Metric)``,
    ``start()``, ``terminate()``, and ``join()``. The first will be called every time a metric needs to be updated,
    ``start()`` is used when the metrics are first loaded, and ``terminate()`` and ``join()`` are called in that
    sequence when shutting down. Since the metrics manager is typically a separate thread, ``terminate()`` should
    instruct the thread to gracefully exit and ``start()`` and ``join()`` should be inherited from ``threading.Thread``.

    ERDDAPUtil provides ``erddaputil.main.metrics.LocalPrometheusSendThread`` which uses the HTTP API's Prometheus
    metrics.

``erddaputil.secret_key``
    This should be a secret that is the same between all servers that will share an AMPQ exchange or daemon
    and is used to validate that the messages passed are not malicious. It should have at least 192 bits of
    randomness.

``erddaputil.show_config``
    Set to ``true`` to dump the configuration to stdout on boot. This is useful for debugging.

``erddaputil.use_ampq_exchange``
    Set this to ``true`` to use the AMPQ features.

``erddaputil.use_local_daemon``
    Set this to ``false`` if you want to only send messages to AMPQ from the CLI or HTTP API.


ERDDAP Configuration
--------------------
``erddaputil.erddap.base_url``
    The base URL for ERDDAP (e.g. ``http://localhost:8080/erddap``). Note that, unlike ERDDAP, this
    should include the ``/erddap`` path.

``erddaputil.erddap.big_parent_directory``
    Set to the same value as ERDDAP's ``bigParentDirectory`` configuration value

``erddaputil.erddap.datasets_d``
    Set to the directory containing XML files with dataset definitions in them. These should be
    identical to the ones created for ERDDAP, but each in their own XML file. Each XML file should
    contain exactly one ``<dataset>`` tag as the root-level element. While ERDDAP requires datasets
    use ISO-8859-1 encoding, these datasets can use any encoding as long as it is declared and
    compatible with ISO-8859-1 (illegal characters will be replaced).

``erddaputil.erddap.datasets_xml_template``
    By default, ERDDAPUtil will use an empty ``<erddapDatasets>`` tag to generate ``datasets.xml``.
    If you want to supply your own template, provide it here. ERDDAPUtil will only modify it by
    (a) adding all of the datasets found in ``datasets.d`` and (b) updating the block and allow lists.
    Your template file may use a different character encoding as long as it is ISO-8859-1 compatible.

``erddaputil.erddap.ip_block_list``
    A path to a text file of IP addresses, ranges, or subnets to block requests from (one entry per
    line). Defaults to ``{BIG_PARENT_DIRECTORY}/.ip_block_list.txt``

``erddaputil.erddap.subscription_block_list``
    A path to a text file of emails to block subscriptions for (one email per line). Defaults to
    ``{BIG_PARENT_DIRECTORY}/.email_block_list.txt``

``erddaputil.erddap.tomcat_gid``
    The group ID that tomcat runs as. This is used only if ``erddaputil.fix_erddap_bpd_permissions`` is
    set to ``true``.

``erddaputil.erddap.tomcat_uid``
    The user ID that tomcat runs as. This is used only if ``erddaputil.fix_erddap_bpd_permissions`` is
    set to ``true``.

``erddaputil.erddap.unlimited_allow_list``
    A path to a text file of IP addresses, ranges, or subnets to allow unlimited access to (one entry
    per line). Defaults to ``{BIG_PARENT_DIRECTORY}/.unlimited_allow_list.txt``

Dataset Management
------------------

``erddaputil.dataset_manager.backups``
    If specified, whenever a new ``datasets.xml`` file is generated, the old one will be backed-up
    into this folder. Backups are cleaned up according to the below retention setting.

``erddaputil.dataset_manager.backup_retention_days``
    Backups of ``datasets.xml`` are deleted after the given number of days. Defaults to ``31``.

``erddaputil.dataset_manager.max_delay_seconds``
    ERDDAPUtil delays briefly before performing a reload of a dataset, in case another similar
    request comes in (e.g. if your automation pipeline is pushing dozens of requests at once).
    This setting allows you to control the longest ERDDAPUtil will wait after the last request
    for a given dataset to be reloaded before it will execute the request. Set to 0 to always
    immediately execute every request for a reload (the default)

``erddaputil.dataset_manager.max_pending``
    ERDDAPUtil delays briefly before performing a reload of a dataset, in case another similar
    request comes in (e.g. if your automation pipeline is pushing dozens of requests at once).
    This setting allows you to control the maximum number of datasets pending reload; once the
    threshold is exceeded, the oldest request is executed immediately. Set to 0 to ignore the
    threshold (the default).

``erddaputil.dataset_manager.max_recompile_delay``
    Similar to how dataset reloads are delayed, recompilation can also be delayed for similar
    reasons. ERDDAPUtil will wait until this many seconds have elapsed since the last request
    for recompilation before actually performing the recompilation. Set to 0 to always
    recompile immediately when requested (the default).

``erddaputil.dataset_manager.skip_misconfigured_datasets``
    When recompiling datasets, users may instruct ERDDAPUtil to either skip datasets that are
    not well-formed XML, raise an error and fail when such a dataset is found, or use the default
    value. This is the default value; set to ``true`` to skip the datasets (the default) or ``false`
    to raise an error. Note that failed datasets are still logged by ERDDAPUtil so they can be
    remedied; if ``false``, this mostly means that ERDDAPUtil will not update ``datasets.xml`` until the
    file is fixed (the default is to omit it from ``datasets.xml``)

Log Management
--------------
``erddaputil.logman.enabled``
    Set to ``false`` to disable log management.

``erddaputil.logman.file_prefixes``
    A list of files to remove by prefix. Includes all of ERDDAP's log files by default.

``erddaputil.logman.retention_days``
    Days to keep ERDDAP log files (i.e. files in ``{BIG_PARENT_DIRECTORY}/logs``) before removing them. Defaults to
    ``31``.

``erddaputil.logman.sleep_time_seconds``
    Number of seconds to wait between log clean-up jobs (defaults to ``3600``)

AMPQ Integration
----------------
``erddaputil.ampq.cluster_name``
    If you are using AMPQ, this should be a unique value for each set of ERDDAP machines that
    should all respond to the same commands.

``erddaputil.ampq.connection``
    Either the ``URLParameters`` string (for pika integration) or the connection string (for Azure Service Bus)

``erddaputil.ampq.create_queue``
    If set to false, prevents ERDDAPUtil from automatically trying to create and bind the queue or
    create the subscription/rules.

``erddaputil.ampq.exchange_name``
    The RabbitMQ exchange name or the Azure Service Bus topic name (defaults to ``erddap_cnc``)

``erddaputil.ampq.hostname``
    If you are using AMPQ, this should be a unique value for each machine. Defaults to the hostname of
    the machine.

``erddaputil.ampq.implementation``
    Set to ``pika`` or ``azure_service_bus`` depending which client library to use.

Web API
-------
``erddaputil.webapp.enable_management_api``
    Set to ``false`` to disable the management API

``erddaputil.webapp.enable_metrics_collector``
    Set to ``false`` to disable the metrics collector (this is like our own pushgateway)

``erddaputil.webapp.iterations_jitter``
    The number of iterations used for PBKDF2 will be the minimum number plus a random
    integer between 0 and this value for each user. Defaults to ``100000``.

``erddaputil.webapp.min_iterations``
    Specify the minimum number of iterations used for PBKDF2. Defaults to ``700000``.

``erddaputil.webapp.password_file``
    Set to the path of a file where passwords for the web API will be stored.

``erddaputil.webapp.password_hash``
    Set to the name of a hash function supported by ``hashlib``. Defaults to ``sha256``.

``erddaputil.webapp.peppers``
    Set to a list of random strings that are hard to guess. The first one will be used to
    create new passwords and they will all be tried when validating a user's password.

``erddaputil.webapp.salt_length``
    The length of the salt for new passwords (in bytes). Defaults to ``16``.

Metrics Manager - LocalPrometheus
---------------------------------
| ``erddaputil.localprom.host``
| ``erddaputil.localprom.port``

    Set to the host and port of the webapp so the daemon can push statistics to it

| ``erddaputil.localprom.username``
| ``erddaputil.localprom.password``

    Set to the username and password to use for the webapp to push statistics to it

``erddaputil.localprom.batch_size``
    The maximum number of metric updates to send it one batch to the web API. Defaults to ``200``.

``erddaputil.localprom.batch_wait_seconds``
    The maximum amount of time to delay sending metrics while waiting for a whole batch.
    Defaults to ``2``.

``erddaputil.localprom.max_retries``
    The maximum number of times to retry sending a batch to the web API before discarding them. Set
    to ``-1`` to retry forever or ``0`` to only try once. When the daemon is being shutdown, this is overridden
    to not retry at all. Defaults to ``3``.

``erddaputil.localprom.max_tasks``
    The maximum number of batches that will be handled at the same time (defaults to 5). Metrics
    wait in a queue while not being handled. Defaults to ``5``.

``erddaputil.localprom.retry_delay_seconds``
    The delay between retries to send metrics. Defaults to ``2``.

Status Scraper
--------------

``erddaputil.status_scraper.enabled``
    Set to ``false`` to disable the scraping of ``status.html``.

``erddaputil.status_scraper.memory_path``
    Set the path of a file where information about the last scrape of status.html
    is stored. Defaults to a location under ERDDAP's ``bigParentDirectory`` if set,
    otherwise you must provide one.

``erddaputil.status_scraper.sleep_time_seconds``
    The time to wait between scrapes. Defaults to ``300`` (every 5 minutes).

``erddaputil.status_scraper.start_delay_seconds``
    The time to wait after startup before starting to scrape to give ERDDAP time to
    boot. Defaults to ``180`` (3 minutes).


Daemon Service
--------------
| ``erddaputil.daemon.host``
| ``erddaputil.daemon.port``
| ``erddaputil.service.host``
| ``erddaputil.service.port``
    These settings control the host and port that the daemon listens on for connections from the
    CLI, AMPQ, or HTTP clients. The ``daemon`` options are used on the client side and the ``service``
    options on the server side. They should typically match.

``erddaputil.service.backlog``
    The backlog of TCP connections that the daemon server will hold.

``erddaputil.service.listen_block_seconds``
    The time to block while waiting for a new connection. Tidying jobs will be run approximately this
    often.
