Clustering ERDDAP
=================
This project starts with an assumption that users will (eventually) want to create a mirror of their ERDDAP with the
same data and configuration (i.e. they want to create a cluster). However, keeping the mirror in sync does not have an
easy solution.

One option would be to replicate the data files and configuration (possibly using ERDDAP's federation capabilities). This
duplication is not necessary, especially since it will come with an increased cost in terms of either hardware (for
on-premise solutions) or cloud storage costs. It also will present challenges when using container management solutions
like Kubernetes as each instance will need to rebuild its data files from a central repository.

The solution embraced by this project is instead to separate the shared data files onto a persistent shared storage
volume (such as an SMB file share) and give each ERDDAP instance ephemeral local storage for caching, logging, and other
options (the ``bigParentDirectory`` of ERDDAP). This greatly reduces the complexities and costs of configuring multiple
ERDDAP servers with the same content with a minimal impact on speed of access.

The major complexity associated with this arrangement is one of how to ensure the configuration is the same between
servers when updating the datasets that are deployed. This tool simplifies this deployment by allowing the ``<dataset>``
XML tags to be defined in a shared location (called ``datasets.d``) and compiled into a local copy of ``datasets.xml``.
It then leverages AMPQ to push a notification to each server to instruct it to recompile its ``datasets.xml`` file. A
web API and a CLI are both provided to facilitate these operations and allow organizations to integrate it with their
deployment framework.

Therefore, when planning your ERDDAP server, we recommend having two directories, one pointing to a fast local ephemeral
storage backend (containing ERDDAP's ``bigParentDirectory``) and one pointing to a shared storage backend (containing
your ``datasets.d`` folder, your data files, and any additional files such as your ISO-19115 metadata files). The
shared storage backend should be mounted at the same directory on every server and ERDDAPUtil installed on every server.

Change Management
-----------------
When a change is deployed to any of the shared content, you then have two options:

1. If you have an AMPQ server available and have connected your ERDDAP servers using it, you can push a message to
   AMPQ to perform the appropriate operation to refresh the server content. This can be sent manually or by using the
   provided :doc:`/cli_api` or :doc:`/web_api` to make the request.
2. If not, you can make an HTTP request to each server to request the operation be performed.


Reverse Proxy Configuration
---------------------------
For ideal performance, the reverse proxy should then be configured to send requests for the same dataset to the same
backup to maximize ERDDAP's use of its own local cache.

In nginx, this can be done as follows (this configuration is untested, let me know if you find issues):

.. code-block:: nginx
   :linenos:

   map $request_uri $erddap_dataset {
        # Griddap and Tabledap matching
        "~*/erddap/griddap/(?<d>[^/]*)/"    $d;
        "~*/erddap/tabledap/(?<d>[^/]*)/"   $d;
        # Fallback to using the IP address to spread other requests around between servers
        default                             $remote_addr;
   }

   upstream erddap {
       # Consistent is important to reduce the remapping when a server is lost
       hash $erddap_dataset consistent;

       server erddap1.example.com;
       server erddap2.example.com;
   }
