AMPQ API
========
The ERDDAPUtil AMPQ integration allows a command executed via the command line or HTTP API to be executed on multiple
ERDDAPUtil instances. In order to function properly, the AMPQ listener needs to be running on each ERDDAP server. The
listener receives messages from two topics: the global topic ``erddap.global`` and the cluster topic ``erddap.cluster.CLUSTER_NAME``.
The cluster name is set via the configuration.

By default, commands sent via both the HTTP and CLI APIs are broadcast to the cluster topic but this can be overridden
(see the API for detail). This is the easiest way to sent AMPQ messages.

AMPQ Configuration
------------------
ERDDAPUtil supports both pika and Azure Service Bus as AMPQ libraries. The same configuration settings are used for both.
The :confval:`erddaputil.ampq.implementation` configuration key can be set to ``pika`` or ``azure_service_bus``.

For RabbitMQ/pika, the connection parameters need to be passed as they would for :external+pika:class:`pika.connection.URLParameters`.
For Azure Service Bus, this is connection string for the Azure library. You can also change the exchange name as needed.

The ``cluster_name`` can be configured but should be the same on all ERDDAP instances that have the same datasets. It
should be a set of alphanumeric characters and underscores.
