Control List Management
=======================

ERDDAP supports three control lists:

1. An allow list of IP addresses that can circumvent ERDDAP's DDoS protection.
2. A block list of IP addresses who cannot make requests.
3. A block list of e-mail addresses who cannot subscribe.

These are defined in the ``datasets.xml`` file. ERDDAPUtil provides additional
tools for managing these lists and ensuring they are the same between servers by
exposing an API to add or remove entries to any of these lists. This API actually
updates a separate text file on the server that is then used when compiling
``datasets.xml`` (see :doc:`/dataset_manager`) to populate the appropriate XML tags.

IP Address Extensions
---------------------
ERDDAP allows only for basic IP addresses to be used, though the block list of IP
addresses also allows for a special "range" format (e.g. ``10.0.*.*``). However, we
note that some use cases will want to use subnets to allow or block ranges that don't
fit ERDDAP's "range" format (which corresponds to the ``/16`` or ``/24`` subnets).

Therefore ERDDAPUtil allows you to specify any mix of subnet ranges, ERDDAP "ranges", or
simple IP addresses. The subnet ranges are expanded to a mix of ERDDAP "ranges" (block
list only) and simple IP addresses. The allow list will also expand ERDDAP "ranges" to
simple IP addresses.

Note that this can lead to a long list of strings. For better blocking, we recommend using
your reverse proxy

Challenges
----------
Given ERDDAP's poor support for subnet ranges, it is probably advisable to perform
the blocking of IP addresses at the reverse proxy level (if one is in use). This
allows for subnets to be blocked more cleanly and will reduce the load on ERDDAP by
preventing those requests from even reaching it.

In addition, we note that ERDDAP's support for DDoS protection is currently challenging
as well in some cases since it is done by limiting requests by IP address but many
research institutions will have a shared IP address for the users at each campus. Managing
DDoS protection at the reverse proxy or other levels may be a better path, but it cannot
be disabled in ERDDAP at the moment. Adding these institutions public IPs to the allow
unlimited list may be one solution or having suitably high settings for managing incoming
requests (in combination with good DDoS protection at other levels).
