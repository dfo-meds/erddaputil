This package provides several useful tools for ERDDAP written in Python

## Installation

You can install this as a Docker container alongside your ERDDAP or on the same 
machine as ERDDAP. If you use Docker, you will need to make sure your ERDDAP
content directory (containing setup.xml and datasets.xml) and BigParentDirectory
are both mounted in both containers.

## Configuration

See `.erddaputil.example.toml` for all the configuration options.


## Metrics

The web application packaged here exposes a Prometheus metrics endpoint and health
check along with endpoints intended to be used by the daemon and batch scripts to 
report their own metrics (similar to a push gateway).

Metrics are available on port 9172 by default; this may be changed in the configuration.

## Daemon

The daemon provided here essentially provides a Docker-ready script that can be run to
perform several automated tasks as needed. Each task is run in its own thread. Tasks
that can be daemonized in this fashion include:

- Cleaning up log files (`logman`)
- Tailing the ERDDAP logs into a different set of files (`logtail`)

If not using Docker, you can use systemd or NSSM to setup the daemon as well on your
system.

## Command Line Tools

To use the command line tools, run `python -m erddap_util COMMAND` (non-Docker) or 
`docker exec CONTAINER_NAME erddap_util COMMAND` (Docker). Tools available are:


### ERDDAP-Related Commands
| Command | Description |
| --- | --- |
| `reload-dataset [-b] [-h] [-i] [-L] DATASET_ID`| Places a flag file for ERDDAP to reload the dataset ASAP. Specify `-b` for a "bad files" reload OR `-h` for a hard reload.|
| `reload-all-datasets [-b] [-h] [-i] [-L]` | Places a flag file for ERDDAP to reload every dataset defined in `datasets.xml`. Takes the same arguments as `reload-dataset`. |
| `compile-datasets [-i] [-L]` | Recompile the datasets from the config directory (see below) and reloads any modified datasets. |
| `activate-dataset [-i] [-L] DATASET_ID` | Sets the `active=True` attribute on the dataset in the config directory (see below), then recompiles the datasets. |
| `deactivate-dataset [-i] [-L] DATASET_ID` | As above but sets `active=False` |
| `block-email [-i] [-L] EMAIL` | Adds an email to the subscription block list, then recompiles the datasets. See notes on the block lists.|
| `block-ip [-i] [-L] IP_ADDRESS` | Adds an IP to the block list, then recompiles the datasets. See notes on the block lists.|
| `allow-unlimited [-i] [-L] IP_ADDRESS` | Adds an IP to the unlimited allow list, then recompiles the datasets. See notes on the block lists. |
| `unblock-email [-i] [-L] EMAIL` | Remove an email from the subscription block list, then recompiles the datasets. See notes on the block lists.|
| `unblock-ip [-i] [-L] IP_ADDRESS` | Remove an IP from the block list, then recompiles the datasets. See notes on the block lists.|
| `remove-unlimited [-i] [-L] IP_ADDRESS` | Remove an IP from the unlimited allow list, then recompiles the datasets. See notes on the block lists. |
| `flush-logs [-L]` | Forces ERDDAP to flush logs to `log.txt` immediately (by requesting the status.html page)|
| `list-datasets` | Lists the datasets available in this ERDDAP. Only works if there is a local ERDDAP server connected to the ERDDAPUtil. |
| `clear-cache [-L] [DATASET_ID]` | Removes all of the files within the `cache` and the `decompressed` directories. If DATASET_ID is specified, only the given dataset is removed.|

Where applicable, specify `-i` to override any delay that might be set and specify `-L` to prevent broadcasting on AMPQ (if configured).

`DATASET_ID` may be either a single dataset ID or a comma-delimited list of them.

### ERDDAPUtil-Related Commands
| Command | Description |
| --- | --- |
| `set-password USERNAME` | Prompts for and then sets the password for a given user for the web application. If the user doesn't exist, it is created. |



## Web API

### Authentication & Authorization

Endpoints that require authentication use standard HTTP Basic authorization. While not ideal, since this API is mostly
for backend usage, it should generally be sufficient. If these endpoints are exposed to the public Internet, HTTPS 
should be used to ensure the credentials remain secure.

```python
import base64

# Example of creating the Authorization header in Python
un = "username"
pw = "password"

credentials = base64.b64decode(f"{un}:{pw}")

headers = {
    "Authorization": f"Base {credentials}"
}
```

### Endpoints

| Endpoint | Body Parameter | Description |
| --- | --- | --- |
| `/datasets` | N/A | List the datasets available on the local ERDDAP server (response parameter `datasets`) |
| `/datasets/reload` | `[dataset_id]`, `[flag]` | Reload the given dataset(s) with the given flag (0 for soft (default), 1 for bad files, 2 for hard). If dataset_id is omitted, all datasets are reloaded. |
| `/datasets/activate` | `dataset_id` | Set the `active` attribute to `True` for the given dataset(s), then recompile. |
| `/datasets/deactivate` | `dataset_id` | Set the `active` attribute to `False` for the given dataset(s), then recompile. |
| `/datasets/compile` | N/A | Recompile the datasets. |
| `/block/ip` | `ip` | Add the given IP to the block list, then recompile the datasets. |
| `/block/email` | `email` | Add the given email to the block list, then recompile the datasets. |
| `/allow/unlimited` | `ip` | Add the given IP to the allow unlimited list, then recompile the datasets.
| `/unblock/ip` | `ip` | Remove the given IP from the block list, then recompile the datasets. |
| `/unblock/email` | `email` | Remove the given email from the block list, then recompile the datasets. |
| `/unallow/unlimited` | `ip` | Remove the given IP from the allow unlimited list, then recompile the datasets.
| `/flush-logs` | N/A | Flush the ERDDAP logs to disk. |
| `/clear-cache` | `[dataset_id]` | Clear the cache and decompressed folders for the given dataset(s), or all datasets if omitted.  |

Each HTTP endpoint takes a JSON request body that specifies additional parameters to pass
to the function. `dataset_id` may be either a single dataset ID (as a string), a comma-delimited list of
them, or an array of dataset IDs


## AMPQ

AMPQ support is still somewhat experimental, but it is intended to allow an administrator to apply the same changes
to multiple ERDDAP servers that exist in a cluster. If configured, the command line and web app tools will pass any
commands they receive to the AMPQ message queue. ERDDAPUtil also listens to the message queue and will execute commands
given to it.

### Support

ERDDAPUtil supports at least RabbitMQ (via `pika`) and Azure Service Bus (via `azure.servicebus`). In this
documentation, the terminology used is that of the RabbitMQ client. For clarity, the meanings are
listed below since these two use significantly different terminology.

* The RabbitMQ "exchange" (of type topic) is a "topic" in Azure Service Bus.
* The RabbitMQ "queue" and "binds" (with appropriate "routing keys") is a "suscription" and associated "rules" (using CorrelationRuleFilter on the "label") in Azure Service Bus

The pika client will create the exchange and queue on start if they don't exist. This feature can
also be enabled for Azure Service Bus if desired.

### Configuration

The topic exchange offers the ability to have "global" messages (sent to the routing key `erddap.global`) which all
ERDDAPUtil instances listening to the exchange will receive and "cluster" messages (sent to `erddap.cluster.CLUSTER_NAME`)
which will only be actioned by ERDDAPUtil instances with the `erddaputil.ampq.cluster_name` configuration
value set to `CLUSTER_NAME`. `CLUSTER_NAME` can be any string appropriate for a routing key in RabbitMQ and a 
message label in Azure Service Bus. We recommend a combination of alphanumeric characters with underscores.

### Sending messages

The easiest way to send a message is to use the web API or the command line API to broadcast the 
message. 

If you want to send one manually, you can use this library to do so by calling the appropriate function. See 
`erddaputil.erddap.commands` for the ERDDAP-related functions.

If you really want to do everything yourself, commands are serialized into the following JSON 
structure:

```json 
{
    "name": "command_name",
    "args": ["arg1", "arg2"],
    "kwargs: {
        "parameter_name": "parameter_value"
    }
}
```

Each command is digitally signed to ensure that arbitrary commands cannot be executed without knowledge
of the secret key. This uses the `itsdangerous` Python library:

```python
import itsdangerous

json_cmd = {"name": "reload_all_datasets", "args": [], "kwargs": {}}
serializer = itsdangerous.URLSafeSerializer("SECRET_KEY", "command_message_serializer")
message = serializer.dumps(json_cmd)
# send message to either erddap.global or erddap.cluster.CLUSTER_NAME
```

Available commands are as follows:

| command_name (arguments) | description |
| --- | --- |
| `reload_dataset(dataset_id: str or iterable, flag: int = 0, flush: bool = False)` | Reloads the dataset(s). Flag should be 0 (soft), 1 (bad files), or 2 (hard). If flush is set, the operation is performed immediately. |  
| `reload_all_datasets(flag: int, flush: bool = False)` | Reload all datasets using the given flag. |
| `compile_datasets(skip_errored_datasets: bool = None, reload_all_datasets: bool = False, flush: bool = False)` | Recompiles the datasets into datasets.xml. If flush is True, this happens immediately, otherwise it is briefly delayed to prevent multiple recompilations in a short time period. If `reload_all_datasets` is set, all datasets are reloaded immediately after. If `skip_errored_datasets` is True, invalid XML file are ignored (if False, they raise an error).|
| `set_active_flag(dataset_id: str or iterable, active_flag: bool, flush: bool = False)` | Sets the active flag on the given dataset(s), then recompiles (immediately if Flush is true) |
| `manage_email_block_list(email_address: str or iterable, block: bool = True, flush: bool = False)` | Blocks an email, then recompiles the datasets. |
| `manage_ip_block_list(ip_address: str or iterable, block: bool = True, , flush: bool = False)` | Blocks an IP address, then recompiles the datasets. |
| `manage_unlimited_allow_list(ip_address: str or iterable, allow: bool = True, , flush: bool = False)` | Adds an IP address to the unlimited list, then recompiles the datasets. |
| `clear_erddap_cache(dataset_id: str or iterable = None)` | Removes all the files in the ERDDAP `cache` and `decompressed` directory (if dataset_id is specified, only for the given datasets.) |
| `flush_logs()` | Flushes the logs to disk immediately |

As is true in the web API, the `dataset_id` parameter may be a single dataset ID as a string, a list of dataset IDs, or 
a comma-delimited list of dataset IDs as a string. Note that the list must be JSON serializable which typically means
a Python `list`.

 
## ERDDAP Configuration Notes


### Dataset Config Directory

Some tools use the pattern of a configuration directory (dataset.d) and a template file (datasets.template.xml) which
are assembled together to create your datasets.xml file. The datasets are appended at the end and can overwrite any 
previous datasets with the same ID.

We recommend the following directory structure for a local setup

```
  - TOMCAT_DIR/content
    - erddap
      | datasets.xml
    - datasets.d
      | dataset_a.xml
      | dataset_b.xml
    - datasets.template.xml    
```

For a setup with multiple ERDDAP nodes sharing configuration and data from the same file share, the following
directory structure can be used

```
  - TOMCAT_DIR/content/erddap
    | datasets.xml
  - SHARED_DRIVE/CLUSTER_NAME
    - datasets.d
      | dataset_a.xml
      | dataset_b.xml
    - datasets.template.xml 
```

Each dataset file file should contain exactly one `<dataset>` tag as ERDDAP would want it with one exception: the 
encoding may be different and must be declared in the xml declaration. ERDDAP only supports ISO-8859-1, so any 
characters used must be supported by ISO-8859-1. The script tools will load it using the declared encoding and convert 
it to ISO-8859-1 for the actual `datasets.xml` file.

### Block and Allow Lists

ERDDAPUtil keeps an additional list of blocked emails and IP addresses, as well as IP addresses allowed unlimited access
to ERDDAP. If there is a list in datasets.template.xml, it is used as well. The `datasets.xml` file needs to be 
recompiled if the block or allow lists are changed manually (the recompilation is automatically done if the CLI or 
web interface is used to add an entry to these lists).

It is worth noting that ERDDAP's handling of IP addresses is somewhat different from traditional methods. Rather than 
using subnet masks, ERDDAP allows ranges of IPs to be specified using asterisks in the last two octets of an IPv4 address
(e.g. `X.Y.*.*` or `X.Y.Z.1*`). Since the main reason to specify a range of IPs is to allow access to an organization
where a range of IPs might be used, such a practice is not ideal as these ranges may only rarely align with actual 
subnet ranges (`X.Y.Z.*` corresponds to `X.Y.Z.0/24` and `X.Y.*.*` corresponds to `X.Y.0.0/16`). A too-broad pattern
may allow unintended access.

ERDDAPUtil supports this format or backwards compatibility, but it also allows subnet masks to be used both for
the unlimited allow list, and the IP block list. These are translated to a complete list of IP addresses for ERDDAP (using
ranges where possible), so their use should be avoided if the subnet mask is large.

In practice, it is probably more convenient (and a better practice) to block IPs using a reverse proxy instead of ERDDAP
itself as they will support it with less overhead on the Tomcat/ERDDAP server.


## Metrics
Metrics from the tools and from ERDDAP are scraped into a single Prometheus endpoint. If desired, you
can create your own metrics handler (e.g. to push to statsd or another source) and override the declared
class.


## TODO List
- Check and cleanup ERDDAP flag files for datasets that no longer exist
- Add MQ API for some tools
