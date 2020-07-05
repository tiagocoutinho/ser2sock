import os
import sys
import runpy
import socket
import select
import logging
import optparse
import contextlib


IPTOS_NORMAL = 0x0
IPTOS_LOWDELAY = 0x10
IPTOS_THROUGHPUT = 0x08
IPTOS_RELIABILITY = 0x04
IPTOS_MINCOST = 0x02


def create_server(
    address, reuse_addr=True, no_delay=True, tos=IPTOS_LOWDELAY, listen=1):
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 if reuse_addr else 0)
    if hasattr(socket, "TCP_NODELAY") and no_delay:
        server.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    if hasattr(socket, "IP_TOS"):
        server.setsockopt(socket.SOL_IP, socket.IP_TOS, tos)
    server.bind(address)
    server.listen(listen)
    return server


def create_serial(address='/tmp/dcp3000-1', **kwargs):
    import serial
    ser = getattr(serial, 'serial_for_url', serial.Serial)
    return ser(address, **kwargs)


class Bridge:

    def __init__(self, config, listener):
        self.config = config
        self.listener = listener
        self.server = None
        self.client = None
        self.serial = None
        self.ensure_server()

    def ensure_serial(self):
        if self.serial is None:
            self.serial = create_serial(**self.config['serial'])
            self.listener[self.serial] = self
        return self.serial

    def ensure_server(self):
        if self.server is None:
            self.server = create_server(**self.config['tcp'])
            self.listener[self.server] = self
        return self.server

    def close_client(self):
        if self.client:
            self.listener.pop(self.client)
            self.client = None

    def close_serial(self):
        if self.serial:
            self.listener.pop(self.serial)
            self.serial = None

    def tcp_to_serial(self):
        data = self.client.recv(1024)
        if data:
            logging.debug('tcp -> serial: %r', data)
            serial = self.ensure_serial()
            serial.write(data)
        else:
            logging.info('client disconnected')
            self.close_client()
            self.close_serial()

    def serial_to_tcp(self):
        data = self.serial.read(self.serial.inWaiting())
        if self.client is None:
            logging.info('serial data discarded (no client): %r', data)
        else:
            logging.debug('serial -> tcp: %r', data)
            self.client.sendall(data)

    def close(self):
        self.close_client()
        self.close_serial()
        self.server.close()

    def accept(self):
        client, addr = self.server.accept()
        if self.client is None:
            logging.info('new connection from %r', addr)
            self.client = client
            self.listener[client] = self
        else:
            logging.info('disconnect client %r (already connected)', addr)
            client.close()

    def on_event(self, source):
        if source is self.server:
            return self.accept()
        elif source is self.client:
            return self.tcp_to_serial()
        elif source is self.serial:
            return self.serial_to_tcp()


def create_bridges(bridges, listener):
    for config in bridges:
        if isinstance(config, (tuple, list)):
            a, b = config
            serial, tcp = (a, b) if a.pop('__kind__') == 'serial' else (b, a)
            b.pop('__kind__')
            config = dict(serial=serial, tcp=tcp)
        yield Bridge(config, listener)


class Server:

    def __init__(self, config):
        self.config = config

    def __enter__(self):
        logging.info('Bootstraping bridges...')

        self.listener = {}
        self.bridges = list(create_bridges(self.config['bridges'], self.listener))
        logging.info('Ready to accept requests!')
        return self

    def __exit__(self, exc_type, exc_value, tb):
        for bridge in self.bridges:
            bridge.close()

    def run(self):
        while True:
            readers, _, _ = select.select(self.listener, (), ())
            for reader in readers:
                bridge = self.listener[reader]
                bridge.on_event(reader)


def load_config(filename):

    def tcp(**kwargs):
        kwargs['__kind__'] = 'tcp'
        return kwargs

    def serial(**kwargs):
        kwargs['__kind__'] = 'serial'
        return kwargs

    glob = dict(serial=serial, tcp=tcp)

    full = os.path.abspath(filename)
    path, fname = os.path.split(filename)
    mod_name, _ = os.path.splitext(fname)
    sys.path.insert(0, path)
    try:
        config = runpy.run_module(mod_name, glob)
    finally:
        sys.path.pop(0)
    return config


def main():
    parser = optparse.OptionParser()
    parser.add_option('-c', '--config', help='config file name')
    options, args = parser.parse_args()
    if options.config is None:
        print('Missing configuration file argument (-c/--config)')
        exit(1)
    config = load_config(options.config)
    try:
        with Server(config) as server:
            server.run()
    except KeyboardInterrupt:
        logging.info('Interrupted. Bailing out...')



if __name__ == "__main__":
    main()
