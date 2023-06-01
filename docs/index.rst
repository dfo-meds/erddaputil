.. ERDDAPUtil documentation master file, created by
   sphinx-quickstart on Wed May 17 13:55:59 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

ERDDAPUtil
==========
ERDDAPUtil provides a set of tools to use with `ERDDAP <https://github.com/ERDDAP/erddap>`_ that provides additional
management tools with a focus on containerization, automation, and clustering. The key features are:

* A pattern for storing dataset definitions in a folder and compiling the ``datasets.xml`` file from it
* Activating, deactivating, and reloading datasets
* Managing the request and subscription block lists, as well as the unlimited access allow list
* Web hooks for requesting dataset compilation, reloading, activation, or deactivation (with authentication)
* AMPQ integration for performing the same operation on multiple servers at once
* Log cleanup and management
* A `Prometheus <https://prometheus.io/>`_-compatible web API that scrapes statistics from ERDDAP

.. toctree::
   :maxdepth: 1
   :caption: Contents:
   :glob:

   overview
   setup
   cli_api
   web_api
   ampq_api
   control_lists
   dataset_manager
   erddap_metrics
   tomtail
   log_management
   config
   clustering
   code/index


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
