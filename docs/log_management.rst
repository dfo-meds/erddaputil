Log Management
==============

By default, ERDDAP maintains only two log files but it copies them upon restart to preserve them in case of an error.
These copies are not pruned by default, nor are other log files generated (such as daily emails).

ERDDAPUtil therefore runs a thread that checks each file in ``BIG_PARENT_DIRECTORY/logs`` for two conditions:

1. Does it start with one of the configured prefixes? These default to "logPreviousArchivedAt", "logArchivedAt", and
   "emailLog"
2. Is its last modified time greater than the configured number of days to retain log files.

If a file matches both of these conditions, it will be removed.
