Setting Up ERDDAPUtil
=====================
ERDDAPUtil is designed to function as a sidecar container to ERDDAP, in that each ERDDAP server should have one
instance of ERDDAPUtil running beside it. ERDDAPUtil will need access to the ``bigParentDirectory`` of ERDDAP, to the
Tomcat configuration, and to data files.

Quick Setup
-----------
1. Create a directory for your project
2. Copy and paste the contents of the compose.yaml file below into ``compose.yaml``
3. Create a subdirectory called ``erddaputil_config``
4. Copy and paste the quick startup configuration below into ``.erddaputil.toml``
5. Run ``docker compose up --detach``
6. ERDDAP will be available on ``http://localhost:8080`` and the metrics/management API on ``http://localhost:9173``


Docker Compose
--------------
This simple example illustrates a minimal configuration for using ERDDAPUtil and ERDDAP
in Docker via a compose file. This file would go in the same directory as a copy of the
ERDDAPUtil repository (later to be released as a Docker Hub image to simplify this).

.. code-block:: yaml
    services:

        # ERDDAP
        erddap:
            image: axiom/docker-erddap:2.23-jdk17-openjdk
            volumes:
                - "ephemeral-data:/erddap_data"
                - "persistent-data:/persistent_data"
                - "erddap-content:/usr/local/tomcat/content/erddap"
            ports:
                - "8080:8080"
            environment:
                - "ERDDAP_bigParentDirectory=/erddap_data"
            networks:
                - erddap-network
            depends_on:
                - erddaputil_daemon

        # Management Daemon
        erddaputil_daemon:
            image: dfomeds/erddaputil:latest
            volumes:
                - "ephemeral-data:/erddap_data"
                - "persistent-data:/persistent_data"
                - "erddap-content:/erddap_content"
                - "./erddaputil_config:/erddap_util/config"
            networks:
                - erddap-network
            depends_on:
                - erddaputil_webapp

        # Web Application
        erddaputil_webapp:
            image: dfomeds/erddaputil:latest
            command: ["webserver"]
            volumes:
                - "ephemeral-data:/erddap_data"
                - "persistent-data:/persistent_data"
                - "erddap-content:/erddap_content"
                - "./erddaputil_config:/erddap_util/config"
            ports:
                - "9173:9173"
            networks:
                - erddap-network

        # AMPQ Listener
        erddaputil_ampq:
            image: dfomeds/erddaputil:latest
            command: ["ampq"]
            volumes:
                - "ephemeral-data:/erddap_data"
                - "persistent-data:/persistent_data"
                - "erddap-content:/erddap_content"
                - "./erddaputil_config:/erddap_util/config"
            networks:
                - erddap-network
            depends_on:
                - erddaputil_daemon

    networks:
        erddap-network:

    volumes:
        ephemeral-data:
        persistent-data:
        erddap-content:

Quickstart Configuration
------------------------
The configuration below should work out-of-the-box for the Docker compose file above. You will need to modify it to suit
your use case.

.. code-block:: toml
    [erddaputil]
    # Change these to something unique and secure in production
    secret_key = "SECRET"
    default_username = "admin"
    default_password = "admin"
    metrics_manager = "erddaputil.main.metrics.LocalPrometheusSendThread"

    [erddaputil.erddap]
    # Adjust to match as needed
    big_parent_directory = "/erddap_data"
    datasets_d = "/persistent_data/datasets.d"
    datasets_xml = "/erddap_content/datasets.xml"  # Points to /usr/local/tomcat/content/erddap/datasets.xml on ERDDAP container
    base_url = "http://erddap:8080/erddap"

    [erddaputil.dataset_manager]
    # Adjust if needed
    backups = "/erddap_data/_dataset_backups"

    [erddaputil.daemon]
    # name of your daemon container here, if on the same network in Docker
    host = "erddaputil_daemon"

    [erddaputil.service]
    host = "0.0.0.0"

    [erddaputil.webapp]
    # Adjust if needed
    password_file = "/erddap_data/.erddaputil_webapp_passwords"

    # Change this and keep it secret
    peppers = ["SECRET2"]

    [erddaputil.localprom]
    # Name of your host here
    host = "erddaputil_webapp"
    port = 9173
    # Use the default_username and default_password here unless you have made another account.
    username = "admin"
    password = "admin"

Configuration
-------------
Configuration is done via a TOML file located at ``.erddaputil.toml`` (using the above Docker
configuration). Use the ``.erddaputil.example.toml`` file to create this. Common settings are below.

``erddaputil.secret_key``
    This should be a secret that is the same between all servers that will share an AMPQ exchange
    and is used to validate that the messages passed are not malicious.

``erddaputil.use_ampq_exchange``
    Set this to true to use the AMPQ features

``erddaputil.use_local_daemon``
    Set this to false if you want to only send messages to AMPQ from the CLI or HTTP API.

``erddaputil.erddap.big_parent_directory``
    Set to the same value as ERDDAP's bigParentDirectory configuration value

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

``erddaputil.erddap.base_url``
    The base URL for ERDDAP (e.g. ``http://localhost:8080/erddap``).

``erddaputil.erddap.subscription_block_list``
    A path to a text file of emails to block subscriptions for (one email per line). Defaults to
    ``{BIG_PARENT_DIRECTORY}/.email_block_list.txt``

``erddaputil.erddap.ip_block_list``
    A path to a text file of IP addresses, ranges, or subnets to block requests from (one entry per
    line). Defaults to ``{BIG_PARENT_DIRECTORY}/.ip_block_list.txt``

``erddaputil.erddap.unlimited_allow_list``
    A path to a text file of IP addresses, ranges, or subnets to allow unlimited access to (one entry
    per line). Defaults to ``{BIG_PARENT_DIRECTORY}/.unlimited_allow_list.txt``

``erddaputil.dataset_manager.backups``
    If specified, whenever a new ``datasets.xml`` file is generated, the old one will be backed-up
    into this folder. Backups are cleaned up according to the below retention setting.

``erddaputil.dataset_manager.backup_retention_days``
    Backups of ``datasets.xml`` are deleted after the given number of days. Defaults to 30.

``erddaputil.dataset_manager.max_pending``
    ERDDAPUtil delays briefly before performing a reload of a dataset, in case another similar
    request comes in (e.g. if your automation pipeline is pushing dozens of requests at once).
    This setting allows you to control the maximum number of datasets pending reload; once the
    threshold is exceeded, the oldest request is executed immediately. Set to 0 to ignore the
    threshold.

``erddaputil.dataset_manager.max_delay_seconds``
    ERDDAPUtil delays briefly before performing a reload of a dataset, in case another similar
    request comes in (e.g. if your automation pipeline is pushing dozens of requests at once).
    This setting allows you to control the longest ERDDAPUtil will wait after the last request
    for a given dataset to be reloaded before it will execute the request. Set to 0 to always
    immediately execute every request for a reload.

``erddaputil.dataset_manager.max_recompile_delay``
    Similar to how dataset reloads are delayed, recompilation can also be delayed for similar
    reasons. ERDDAPUtil will wait until this many seconds have elapsed since the last request
    for recompilation before actually performing the recompilation. Set to 0 to always
    recompile immediately when requested.

``erddaputil.dataset_manager.skip_misconfigured_datasets``
    When recompiling datasets, users may instruct ERDDAPUtil to either skip datasets that are
    not well-formed XML, raise an error and fail when such a dataset is found, or use the default
    value. This is the default value; set to true to skip the datasets (the default) or false
    to raise an error. Note that failed datasets are still logged by ERDDAPUtil so they can be
    remedied; if the "fail" option is chosen, this mostly means that ERDDAPUtil will not
    update ``datasets.xml`` until the file is fixed (the default is to omit it from ``datasets.xml``)

``erddaputil.logman.enabled``
    Set to false to disable log management

``erddaputil.logman.retention_days``
    Days to keep ERDDAP log files (i.e. files in ``{BIG_PARENT_DIRECTORY}/logs``) before removing them.

``erddaputil.logman.file_prefixes``
    A list of files to remove by prefix. Includes all of ERDDAP's log files by default.

``erddaputil.ampq.cluster_name``
    If you are using AMPQ, this should be a unique value for each set of ERDDAP machines that
    should all respond to the same commands.

``erddaputil.ampq.hostname``
    If you are using AMPQ, this should be a unique value for each machine. Defaults to the hostname of
    the machine.

``erddaputil.ampq.connection``
    Either the URLParameters string (for pika integration) or the connection string (for Azure Service Bus)

``erddaputil.ampq.exchange_name``
    The RabbitMQ exchange name or the Azure Service Bus topic name (defaults to erddap_cnc)

``erddaputil.ampq.create_queue``
    If set to false, prevents ERDDAPUtil from automatically trying to create and bind the queue or create the subscription/rules.

``erddaputil.ampq.implementation``
    Set to ``pika`` or ``azure_service_bus`` depending which client library to use.

``erddaputil.webapp.password_file``
    Set to the path of a file where passwords for the web API will be stored.

``erddaputil.webapp.peppers``
    Set to a list of random strings that are hard to guess. The first one will be used to
    create new passwords and they will all be tried when validating a user's password.

``erddaputil.webapp.enable_metrics_collector``
    Set to false to disable the metrics collector (this is like our own pushgateway)

``erddaputil.webapp.enable_management_api``
    Set to false to disable the management API

| ``erddaputil.localprom.host``
| ``erddaputil.localprom.port``

    Set to the host and port of the webapp so the daemon can push statistics to it

| ``erddaputil.localprom.username``
| ``erddaputil.localprom.password``

    Set to the username and password to use for the webapp to push statistics to it

| ``erddaputil.daemon.host``
| ``erddaputil.daemon.port``
| ``erddaputil.service.host``
| ``erddaputil.service.port``

    These settings control the host and port that the daemon listens on for connections from the
    CLI, AMPQ, or HTTP clients. The daemon options are used on the client side and the service
    options on the server side. They should typically match.


