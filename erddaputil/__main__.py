import sys


def _launch_cli():
    from erddaputil.cli.cli import base
    base()


def _launch_daemon():
    from erddaputil.main.manager import Application
    app = Application()
    app.run_forever()


def _launch_ampq():
    from erddaputil.ampq import AmpqReceiver
    receiver = AmpqReceiver()
    receiver.run_forever()


def _launch_webapp():
    from waitress.runner import run
    args = [
        sys.argv[0],
        "--host", "0.0.0.0",
        "--port", "9173",
        "--threads", "1",
    ]
    if len(sys.argv) > 1:
        args.extend(sys.argv[1:])
    args.append("erddaputil.webapp.app:default_app")
    run(args)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ('daemon', 'webserver', 'ampq', 'cli'):
        service = sys.argv[1]
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        if service == 'daemon':
            _launch_daemon()
        elif service == 'webserver':
            _launch_webapp()
        elif service == 'ampq':
            _launch_ampq()
        elif service == 'cli':
            _launch_cli()
    else:
        _launch_cli()
