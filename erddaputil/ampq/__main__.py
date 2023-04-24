

if __name__ == "__main__":
    from erddaputil.ampq.ampq import AmpqReceiver
    app = AmpqReceiver()
    app.run_forever()
