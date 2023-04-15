This package provides several useful tools for ERDDAP written in Python

## Installation

You can install this as a Docker container alongside your ERDDAP or on the same 
machine as ERDDAP. If you use Docker, you will need to make sure your ERDDAP
content directory (containing setup.xml and datasets.xml) and BigParentDirectory
are both mounted in both containers.

## Web Application

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

| Command | Description |
| --- | --- |
| `reload-dataset DATASET_ID FLAG` | Places a flag file for ERDDAP to reload the dataset ASAP. FLAG can be set to 0 (normal flag), 1 (bad files flag), or 2 (hard flag) |
| `compile-datasets` | Recompile the datasets from the config directory (see below) and reloads any modified datasets. |
| `activate-dataset DATASET_ID` | Sets the active=True flag on the dataset in the config directory (see below) and reloads it if needed. |
| `deactivate-dataset DATASET_ID` | As above but active=False |

### Dataset Config Directory

Some tools use the pattern of a configuration directory (dataset.d) and a template file (datasets.template.xml) which
are assembled together to create your datasets.xml file. The datasets are appended at the end and can overwrite any 
previous datasets with the same ID.

We recommend the following directory structure:

```
  - erddap
    - content
      | datasets.xml
    - datasets.d
      | dataset_a.xml
      | dataset_b.xml
    - datasets.template.xml    
```

Each file should contain exactly one `<dataset>` tag as ERDDAP would want it with one exception: the encoding may be
different and must be declared in the xml declaration. ERDDAP only supports ISO-8859-1, so any characters used must be
supported by ISO-8859-1. The script tools will load it using the declared encoding and convert it to ISO-8859-1 for the
actual `datasets.xml` file.

## Metrics
Metrics from the tools and from ERDDAP are scraped into a single Prometheus endpoint. If desired, you
can create your own metrics handler (e.g. to push to statsd or another source) and override the declared
class.


## todo
- Check and cleanup ERDDAP flag files for datasets that no longer exist
- Add web UI for some tools
- Add MQ API for some tools
- 