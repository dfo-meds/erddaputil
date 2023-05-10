"""Executes the module by importing and running the AmpqReceiver class"""

if __name__ == "__main__":
    from erddaputil.common import init_config
    init_config()

    from erddaputil.ampq import AmpqReceiver
    receiver = AmpqReceiver()
    receiver.run_forever()
