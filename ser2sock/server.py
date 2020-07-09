import os
import sys
import runpy
import socket
import select
import logging
import optparse

PY2 = sys.version_info[0] == 2

if PY2:
    import selectors2 as selectors  # pragma: no cover
else:
    import selectors

import serial

from .bridge import Bridge
from .config import load_config, to_bridge


class Server:

    shutdown_message = b"shutdown"

    def __init__(self, config):
        self.config = config
        self.selector = selectors.DefaultSelector()

    def __enter__(self):
        logging.info("Bootstraping bridges...")
        self._make_self_channel()
        self._make_bridges()
        self.run_flag = True
        logging.info("Ready to accept requests!")
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.close()

    def close(self):
        for bridge in self.bridges:
            bridge.close()
        self._close_self_channel()
        self.selector.close()

    def _make_bridges(self):
        self.bridges = [Bridge(config, self) for config in self.config["bridges"]]

    def _make_self_channel(self):
        self._ssock, self._csock = socket.socketpair()
        self._ssock.setblocking(False)
        self._csock.setblocking(False)
        self.add_reader(self._ssock, self._on_internal_event)

    def _close_self_channel(self):
        self.remove_reader(self._ssock)
        self._ssock.close()
        self._ssock = None
        self._csock.close()
        self._csock = None

    def _on_internal_event(self, fd):
        data = fd.recv(4096)
        if data == self.shutdown_message:
            self.run_flag = False

    def add_reader(self, reader, cb):
        self.selector.register(reader, selectors.EVENT_READ, cb)

    def remove_reader(self, reader):
        if reader in self.selector.get_map():
            self.selector.unregister(reader)
            return True
        return False

    def step(self):
        events = self.selector.select()
        for key, mask in events:
            key.data()

    def run(self):
        while self.run_flag:
            self.step()
        self.close()

    def stop(self):
        if self._csock:
            self._csock.sendall(self.shutdown_message)

    def reconfig(self, config):
        for bridge, config in zip(self.bridges, config["bridges"]):
            bridge.reconfig(config)


SERVER = None


def run(options):
    global SERVER
    config = load_config(options.config)
    try:
        with Server(config) as server:
            SERVER = server
            if config["web"]:
                from .web import run

                run(server, config)
            else:
                server.run()
    except KeyboardInterrupt:  # pragma: no cover
        logging.info("Interrupted. Bailing out...")
    finally:
        SERVER = None


def main(args=None):
    parser = optparse.OptionParser()
    parser.add_option("-c", "--config", help="config file name")
    options, args = parser.parse_args(args)
    if options.config is None:
        parser.error("Missing configuration file argument (-c/--config)")
    run(options)


if __name__ == "__main__":
    main()  # pragma: no cover
