#! /bin/sh

cd /erddap_util

if [ "$1" = 'webserver' ]; then
  shift
  # TODO: convert to gunicorn?
  python -m flask --app erddaputil.webapp.app run -h "0.0.0.0" -p 9172 "$@"

elif [ "$1" = 'daemon' ]; then
  shift
  python -m erddaputil "$@"

else
  python -m erddaputil.cli "$@"

fi
