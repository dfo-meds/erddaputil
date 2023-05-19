Web API
=======

Requests
--------

All requests must be authenticated using HTTP Basic Auth with UTF-8 encoded usernames
and passwords. Usernames and passwords can be created using the :doc:`/cli_api`.

As an example of sending a request:

.. code-block:: python

   import requests
   import base64

   username = "admin"
   password = "admin"
   un_pw = f"{username}:{password}
   headers = {
     "Authorization": f"basic {base64.b64encode(un_pw.encode('utf-8'))}
   }
   resp = requests.post(
       "http://erddaputil_web/datasets/reload",
       headers=headers,
       json={
           "dataset_id": "mydataset,mydataset2",  # Dataset IDs to reload
           "flag": 1,                             # Do a "bad files" reload
           "_broadcast": 2                        # Sent the message globally
       }
   )

   # resp will look like:
   # { "success": true, "message": "success" }



Endpoints
---------

datasets
^^^^^^^^

.. code-block::

   GET /datasets

Lists the datasets that are available. A local daemon must be running. The dataset IDs are
listed in the ``datasets`` key of the returned JSON object.

datasets/reload
^^^^^^^^^^^^^^^

.. code-block::

   POST /datasets/reload
   { "_broadcast": 1, "flag": 0, "dataset_id": "..." }

Reloads one or more datasets. ``flag`` defaults to ``0`` (soft reload) but may also be
``1`` (bad files reload) or ``2`` (hard reload).

``dataset_id`` may be a single dataset ID, a comma-delimited list of them, or a JSON list
of them. If ``dataset_id`` is missing or empty, it defaults to reloading all of the datasets.

Broadcast can be set to ``0`` (no broadcast via AMPQ), ``1`` (cluster broadcast, default),
or ``2`` (global broadcast).

datasets/activate
^^^^^^^^^^^^^^^^^

.. code-block::

   POST /datasets/activate
   { "_broadcast": 1, "dataset_id": "..." }

Activates one or more datasets.

``dataset_id`` may be a single dataset ID, a comma-delimited list of them, or a JSON list
of them.

Broadcast can be set to ``0`` (no broadcast via AMPQ), ``1`` (cluster broadcast, default),
or ``2`` (global broadcast).

datasets/deactivate
^^^^^^^^^^^^^^^^^^^

.. code-block::

   POST /datasets/deactivate
   { "_broadcast": 1, "dataset_id": "..." }

Deactivates one or more datasets.

``dataset_id`` may be a single dataset ID, a comma-delimited list of them, or a JSON list
of them.

Broadcast can be set to ``0`` (no broadcast via AMPQ), ``1`` (cluster broadcast, default),
or ``2`` (global broadcast).

datasets/compile
^^^^^^^^^^^^^^^^

.. code-block::

   POST /datasets/compile
   { "_broadcast": 1 }

Compiles the ``datasets.xml`` file.

Broadcast can be set to ``0`` (no broadcast via AMPQ), ``1`` (cluster broadcast, default),
or ``2`` (global broadcast).

block/ip
^^^^^^^^

.. code-block::

   POST /block/ip
   { "ip": "...", "_broadcast": 1 }

Blocks one or more IP addresses

``ip`` may be an IP address, an ERDDAP range of IP addresses, a subnet mask, a comma-delimited
list of addresses, ranges, or subnets, or a JSON list of addresses, ranges, or subnets.

Broadcast can be set to ``0`` (no broadcast via AMPQ), ``1`` (cluster broadcast, default),
or ``2`` (global broadcast).

unblock/ip
^^^^^^^^^^

.. code-block::

   POST /unblock/ip
   { "ip": "...", "_broadcast": 1 }

Unlocks one or more IP addresses

``ip`` may be an IP address, an ERDDAP range of IP addresses, a subnet mask, a comma-delimited
list of addresses, ranges, or subnets, or a JSON list of addresses, ranges, or subnets.

Broadcast can be set to ``0`` (no broadcast via AMPQ), ``1`` (cluster broadcast, default),
or ``2`` (global broadcast).

block/email
^^^^^^^^^^^

.. code-block::

   POST /block/email
   { "email": "...", "_broadcast": 1 }

Blocks one or more email addresses.

`email` may be a single email address, a comma-delimited list of email addresses (note that
ERDDAP does not allow commas in emails even though they are valid characters), or a JSON list
of email addresses.

Broadcast can be set to ``0`` (no broadcast via AMPQ), ``1`` (cluster broadcast, default),
or ``2`` (global broadcast).

unblock/email
^^^^^^^^^^^^^

.. code-block::

   POST /unblock/email
   { "email": "...", "_broadcast": 1 }

Unblocks one or more email addresses.

`email` may be a single email address, a comma-delimited list of email addresses (note that
ERDDAP does not allow commas in emails even though they are valid characters), or a JSON list
of email addresses.

Broadcast can be set to ``0`` (no broadcast via AMPQ), ``1`` (cluster broadcast, default),
or ``2`` (global broadcast).

allow/unlimited
^^^^^^^^^^^^^^^

.. code-block::

   POST /allow/unlimited
   { "ip": "...", "_broadcast": 1 }

Adds an IP address to the unlimited list.

``ip`` may be an IP address, an ERDDAP range of IP addresses, a subnet mask, a comma-delimited
list of addresses, ranges, or subnets, or a JSON list of addresses, ranges, or subnets.

Broadcast can be set to ``0`` (no broadcast via AMPQ), ``1`` (cluster broadcast, default),
or ``2`` (global broadcast).

unallow/unlimited
^^^^^^^^^^^^^^^^^

.. code-block::

   POST /unallow/unlimited
   { "ip": "...", "_broadcast": 1 }

Removes an IP address from the unlimited list.

``ip`` may be an IP address, an ERDDAP range of IP addresses, a subnet mask, a comma-delimited
list of addresses, ranges, or subnets, or a JSON list of addresses, ranges, or subnets.

Broadcast can be set to ``0`` (no broadcast via AMPQ), ``1`` (cluster broadcast, default),
or ``2`` (global broadcast).

flush-logs
^^^^^^^^^^

.. code-block::

   POST /flush-logs
   { "_broadcast": 1 }

Flushes the logs of the ERDDAP server.

Broadcast can be set to ``0`` (no broadcast via AMPQ), ``1`` (cluster broadcast, default),
or ``2`` (global broadcast).

clear-cache
^^^^^^^^^^^

.. code-block::

   POST /clear-cache
   { "dataset_id": "...", "_broadcast": 1 }

Removes all decompressed files for one or more datasets. If ``dataset_id``
is not provided, it defaults to all datasets.

``dataset_id`` may be a single dataset ID, a comma-delimited list of them, or a JSON list
of them. If ``dataset_id`` is missing or empty, it defaults to removing all of the decompressed
files.

Broadcast can be set to ``0`` (no broadcast via AMPQ), ``1`` (cluster broadcast, default),
or ``2`` (global broadcast).
