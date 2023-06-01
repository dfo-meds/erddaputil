# ERDDAPUtil
ERDDAPUtil provides additional tools for managing an ERDDAP installation which focus on:

* Managing ERDDAP in a Kubernetes environment with high availability
* Automating the deployment of new datasets and updated files for ERDDAP to serve
* Obtaining statistics from ERDDAP in a more common format

The tool is divided into four main components:

* The ERDDAPUtil service (or daemon) which performs management operations.
* A command line interface for the ERDDAPUtil service
* A web interface for the ERDDAPUtil service that also provides Prometheus metrics
* An AMPQ worker service that listens for AMPQ messages and interfaces with the ERDDAPUtil service

[Documentation](https://erddaputil.readthedocs.io/en/latest)

## Installation
ERDDAPUtil can be installed as a Python package via `python -m pip install erddaputil`. It
is also available as a Docker image `dfomeds/erddaputil`.

Visit the [Quickstart Guide](https://erddaputil.readthedocs.io/en/latest/setup.html) to obtain
details on getting starting with the tool.

For most features, ERDDAPUtil requires access to the ERDDAP and Tomcat directory structures 
so that it can access and modify files. It should therefore be installed on the same physical
server or in the same Kubernetes Pod as ERDDAP.


## Features

### ERDDAP Management Features
* Trigger dataset reload, including a "badFiles" or a "hard" reload
* Compile ERDDAP's `dataset.xml` file from a directory of XML files
* Block or unblock IP addresses and emails in ERDDAP's `dataset.xml` file
* Add or remove IP addresses from the unlimited requests entry in `datasets.xml` 
* Scrape ERDDAP's `status.html` page and turn it into Prometheus statistics
* Scrape Tomcat's access logs and turn them into Prometheus statistics
* Remove old log files from Tomcat and ERDDAP
  
### Additional Features
* Execute ERDDAP management commands (reloads, compiles, blocks, unblocks) from the command 
  line or by authenticated HTTP request
* Define clusters of ERDDAP servers and pass all commands executed on one server to all other 
  servers in the cluster (requires RabbitMQ or Azure Service Bus)
  


