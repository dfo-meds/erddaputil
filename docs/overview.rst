Overview
========
ERDDAPUtil provides additional management features for ERDDAP designed for use cases that
focus on automated deployment and update of datasets to an ERDDAP server and for clustering
use cases. However, these features can be used with any standard ERDDAP server if desired.

Installation
------------
We recommend installation via Docker or another containerized approach, however it is possible
to clone the `source repository <https://github.com/dfo-meds/erddaputil>`_ to your server and
use the tools manually.

Docker
^^^^^^
A `Docker image <https://hub.docker.com/r/dfomeds/erddaputil>`_ is provided for ease of use.

The :doc:`/setup` can be used for a quick introduction to using this image via Compose.

ERDDAPUtil Service
------------------
The ERDDAPUtil service performs all operations related to ERDDAP such as reloading datasets,
compiling ``datasets.xml``, and other tasks. It is organized this way so that only a single
operation is executed at once on the file system to avoid the AMPQ, HTTP, and CLI APIs from
creating race conditions or other conflicts. Each API communicates with the daemon over a
TCP connection (by default on port 9172) to request an operation be performed.

The ERDDAP tools currently included are:

* Requesting a dataset be reloaded ASAP at any of the three levels that ERDDAP allows (see :doc:`/dataset_manager`)
* Recompiling the datasets.xml file from a directory of XML files (see :doc:`/dataset_manager`)
* Flushing the log files to disk (see :doc:`/dataset_manager`)
* Listing the datasets currently in datasets.xml (see :doc:`/dataset_manager`)
* Blocking and unblocking IP addresses from making requests (see :doc:`/control_lists`)
* Blocking and unblocking emails from subscribing (see :doc:`/control_lists`)
* Adding and removing IP addresses from the allow unlimited requests list (see :doc:`/control_lists`)
* Parsing the status.html page and creating Prometheus metrics from it (see :doc:`/erddap_metrics`)
* Removing old log files from ERDDAP's logs directory (see :doc:`/log_management`)
* Removing decompressed files from ERDDAP's decompressed directory (see :doc:`/dataset_manager`

The service is launched by calling the ERDDAPUtil Python module and it must be running for
any of the other APIs to work.

.. code-block:: Shell

   python -m erddaputil daemon

In Docker, this is the default command when running the container.

Web API
-------
The ERDDAPUtil web API is implemented in Flask and provides several useful tools:

1. A management API that sends commands to the ERDDAPUtil service
2. A metrics API that allows the ERDDAPUtil service to expose metrics via a Prometheus endpoint as well
   as metrics about the web API itself.
3. A health check endpoint

All calls to the management API or to push metrics must be authenticated using HTTP Basic Auth. It runs on port 9173
by default.

The web application can be launched via ``waitress`` (using a single thread) with the command:

.. code-block:: Shell

   python -m erddaputil webserver

In Docker, specify ``command: ['webserver']`` to run the webserver in ``waitress``.

See :doc:`/web_api` for more details.

CLI API
-------
The ERDDAPUtil command line interface is implemented in Click and provides an interface for the
ERDDAPUtil service. The CLI can be called using the command:

.. code-block:: Shell

   python -m erddaputil [COMMAND]

In Docker, it can be executed on the daemon's running container as follows:

.. code-block:: Shell

   docker exec erddaputil_daemon python -m erddaputil [COMMAND]

See :doc:`/cli_api` for more details.

AMPQ Integration
----------------
ERDDAPUtil is designed to support sending the same command to multiple ERDDAP servers at once.
The ERDDAPUtil service provides this functionality by sending a message via AMPQ whenever a
command is received if configured to do so. Any ERDDAPUtil instance running its AMPQ listener will
receive such messages and apply the same action but not rebroadcast it (the local server is configured
to ignore its own AMPQ messages so the action is not applied twice).

The AMPQ listener can be run with the following command:

.. code-block:: Shell

   python -m erddaputil ampq

In Docker, specify ``command: ['ampq']`` to run the AMPQ service.

See :doc:`/ampq_api` for more details.
