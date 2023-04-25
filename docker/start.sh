#! /bin/sh

cd /erddap_util

if [ "$1" = 'webserver' ]; then
  shift
  python -m waitress --host "0.0.0.0" --port 9173 --threads 1 "$@" erddaputil.webapp.app:create_app

elif [ "$1" = 'daemon' ]; then
  shift
  python -m erddaputil "$@"

elif [ "$1" = 'ampq' ]; then
  shift
  python -m erddaputil.ampq "$@"

else
  python -m erddaputil.cli "$@"

fi
