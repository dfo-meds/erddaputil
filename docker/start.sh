#! /bin/sh

cd /erddap_util

if [ "$1" = 'webserver' ]; then
  shift
  # TODO: convert to gunicorn?
  python -m flask --app erddap_util.app.app run -h "0.0.0.0" -p 9172 "$@"
else
  python -m erddap_util "$@"
fi
