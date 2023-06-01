Quick Start Guide
=================
ERDDAPUtil is designed to function as a sidecar container to ERDDAP, in that each ERDDAP server should have one
instance of ERDDAPUtil running beside it. ERDDAPUtil will need access to the ``bigParentDirectory`` of ERDDAP, to the
Tomcat configuration, and to data files.

Instructions
------------

You will need to have `Docker <https://www.docker.com/>`_ installed on your machine.

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

        # AMPQ Listener (example only)
        # You will need either a pika-compatible AMPQ server (e.g. RabbitMQ) or Azure Service Bus to
        # use this and additional configuration. It is provided here for illustration purposes.
        #erddaputil_ampq:
        #    image: dfomeds/erddaputil:latest
        #    command: ["ampq"]
        #    volumes:
        #        - "ephemeral-data:/erddap_data"
        #        - "persistent-data:/persistent_data"
        #        - "erddap-content:/erddap_content"
        #        - "./erddaputil_config:/erddap_util/config"
        #    networks:
        #        - erddap-network
        #    depends_on:
        #        - erddaputil_daemon

    networks:
        erddap-network:

    volumes:
        ephemeral-data:
        persistent-data:
        erddap-content:

Quickstart Configuration
------------------------
The configuration below should work out-of-the-box for the Docker compose file above. You will need to modify it to suit
your use case. You can also provide configuration as environment variables if preferred by concatenating the section name
with a dot and the key name, then replacing the dots with underscores (e.g. for "big_parent_directory" the environment
variable is named ``ERDDAPUTIL_ERDDAP_BIG_PARENT_DIRECTORY``. This does not work for configuration options that are
lists, such as the peppers.

.. code-block:: toml

    [erddaputil]
    show_config = true
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

Pip Installation
----------------
ERDDAPUtil can also be installed as a Python module from pip:

.. code-block:: Shell

   python -m pip install erddaputil


Configuration for the Python module is in the file ``.erddaputil.toml`` in either the user's
home directory or the current working directory. Configuration can also be done via environment
variables.

The Python module includes the CLI as well as the daemon, webapp, and AMPQ listener which can
be called by the module:

.. code-block:: Shell

   # Daemon launching
   python -m erddaputil daemon

   # Web app (you need extras)
   python -m pip install erddaputil[webapp]
   python -m erddaputil webapp

   # AMPQ listener (you need extras)
   python -m pip install erddaputil[asb]
   # OR
   python -m pip install erddaputil[rabbitmq]
   python -m erddaputil ampq

   # CLI interface
   python -m erddaputil cli [CLI ARGS AND OPTIONS]
