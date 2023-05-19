Dataset Management
==================
The dataset management tools in ERDDAPUtil focus on two key tasks: setting flags to reload datasets and managing the
contents of the ``datasets.xml`` file. These are referred to as "reloading" and "recompiling" respectively.

Dataset Reloading
-----------------
Reloading a dataset simply creates a file in the appropriate place for ERDDAP to see it and start a minor load of that
dataset. This location depends on the type of reload requested:

1. "Soft" reload (``flag`` directory): This is the default and simply scans for new files to add.
2. "Bad Files" reload (``badFilesFlag`` directory): This also removes ERDDAP's list of bad files and forces it to reload them
3. "Hard" reload (``hardFlag`` directory): This removes the dataset from ERDDAP and reloads it. Note that caches of the decompressed files are NOT cleared.

Dataset Compilation
-------------------
Compiling ``datasets.xml`` is a process unique to ERDDAPUtil. It generates the contents of the ``datasets.xml`` file
from various sources, backs up the current one, replaces it, then prompts a reload of the file.

The base information comes from a template file (``datasets.template.xml``) that can contain any valid XML for the final
file. It is supplemented by adding the control lists maintained by ERDDAPUtil (see :doc:`/control_lists`) and the contents
of all valid XML files within the ``datasets.d`` directory.

A valid XML file in ``datasets.d`` must be well-formed and have a single ``<dataset>`` root tag that contains the content
for an ERDDAP dataset (as would be put into ``datasets.xml`` normally). Only one dataset per file is allowed.

ERDDAPUtil offers you a choice on how to react to an invalid file in ``datasets.d``. The default is to ignore it and emit
an error message. However, you can set ``erddaputil.dataset_manager.skip_misconfigured_datasets`` to ``false`` to
instead abort the compilation process.

Of note, both the template and individual dataset files may use other encodings other than the default ISO-8859-1 that
ERDDAP requires. However, the compiled file is converted to ISO-8859-1, so the encodings used must be
compatible.

Backups of the old ``datasets.xml`` file are kept for the given retention period (defaults to 31 days).

The compilation process also compares the old and new definitions of datasets when recompiling. If a definition has
changed, it will automatically execute a hard reload of the dataset. This is often necessary to pick up major changes
to the definition. A reload of all datasets can also be requested at the same time.

Dataset Activation/Deactivation
-------------------------------
This tool will search ``datasets.d`` for the definition of a dataset and change its ``active`` flag accordingly. If any
changes are made, it will then recompile ``datasets.xml`` and prompt a reloading of the changed dataset.

List Datasets
-------------
This tool will scan ``datasets.xml`` and output the IDs of all of the datasets found. Note that this does not use the
AMPQ interface and can only talk to the local ERDDAPUtil daemon to obtain datasets.

Log Flushing
------------
This tool simply requests the URL ``{BASE_URL}/status.html`` which forces ERDDAP to write its logs to disk.

Cache Clearing
--------------
This tool erases the contents of the ``decompressed`` directory. This is only necessary if you have made a change
to an ERDDAP data file that is compressed. Other caches may later be targetted if they can be made to work.






