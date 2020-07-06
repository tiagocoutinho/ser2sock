import os
import sys
import runpy
import socket
import select
import logging
import optparse
import contextlib

PY2 = sys.version_info[0] == 2

if PY2:
    import selectors2 as selectors  # pragma: no cover
else:
    import selectors

__version__ = "2.0.0"

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
    server.setblocking(False)
    return server


def create_serial(address, **kwargs):
    import serial
    ser = getattr(serial, 'serial_for_url', serial.Serial)
    return ser(address, **kwargs)


class Bridge:

    def __init__(self, config, server):
        self.config = config
        self.server = server
        self.sock = None
        self.client = None
        self.serial = None
        self.ensure_server()

    def ensure_serial(self):
        if self.serial is None:
            self.serial = create_serial(**self.config['serial'])
            self.server.add_reader(self.serial, self.serial_to_tcp)
        return self.serial

    def ensure_server(self):
        if self.sock is None:
            self.sock = create_server(**self.config['tcp'])
            self.server.add_reader(self.sock, self.accept)
        return self.sock

    def close_client(self):
        if self.client:
            self.server.remove_reader(self.client)
            self.client.close()
            self.client = None

    def close_serial(self):
        if self.serial:
            self.server.remove_reader(self.serial)
            self.serial.close()
            self.serial = None

    def close_server(self):
        if self.sock:
            self.server.remove_reader(self.sock)
            self.sock.close()
            self.sock = None

    def tcp_to_serial(self, client):
        try:
            self._tcp_to_serial(client)
        except Exception as error:
            logging.error('error tcp -> serial: %r', error)
            self.close_serial()
            self.close_client()

    def _tcp_to_serial(self, client):
        data = client.recv(1024)
        if data:
            logging.debug('tcp -> serial: %r', data)
            self.serial.write(data)
        else:
            raise RuntimeError('Connection closed')

    def serial_to_tcp(self, serial):
        try:
            self._serial_to_tcp(serial)
        except Exception as error:
            logging.error('error reading from serial %r', error, exc_info=1)
            self.close_client()
            self.close_serial()
            return

    def _serial_to_tcp(self, serial):
        data = self.serial.read(self.serial.inWaiting())
        if self.client is None:
            logging.info('serial data discarded (no client): %r', data)
        else:
            logging.debug('serial -> tcp: %r', data)
            self.client.sendall(data)

    def close(self):
        self.close_client()
        self.close_serial()
        self.close_server()

    def accept(self, sock):
        client, addr = sock.accept()
        if self.client is None:
            logging.info('new connection from %r', addr)
            try:
                serial = self.ensure_serial()
            except Exception as error:
                logging.error('error openning serial port %r', error)
                client.close()
                return
            self.client = client
            self.client.setblocking(False)
            self.server.add_reader(client, self.tcp_to_serial)
        else:
            logging.info('disconnect client %r (already connected)', addr)
            client.close()


def make_bridge(config, server):
    if isinstance(config, (tuple, list)):
        a, b = config
        serial, tcp = (a, b) if a.pop('__kind__') == 'serial' else (b, a)
        b.pop('__kind__')
        config = dict(serial=serial, tcp=tcp)
    return Bridge(config, server)


class Server:

    shutdown_message = b'shutdown'

    def __init__(self, config):
        self.config = config
        self.selector = selectors.DefaultSelector()

    def __enter__(self):
        logging.info('Bootstraping bridges...')
        self._make_self_channel()
        self._make_bridges()
        self.run_flag = True
        logging.info('Ready to accept requests!')
        return self

    def __exit__(self, exc_type, exc_value, tb):
        for bridge in self.bridges:
            bridge.close()
        self._close_self_channel()
        self.selector.close()

    def _make_bridges(self):
        self.bridges = [
            make_bridge(config, self)
            for config in self.config['bridges']
        ]

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
        self.selector.unregister(reader)

    def step(self):
        events = self.selector.select()
        for key, mask in events:
            handler, reader = key.data, key.fileobj
            handler(reader)

    def run(self):
        while self.run_flag:
            self.step()

    def stop(self):
        if self._csock:
            self._csock.sendall(self.shutdown_message)

    @property
    def _listener(self):
        return self.selector.get_map()


def tcp(**kwargs):
    kwargs['__kind__'] = 'tcp'
    return kwargs


def serial(**kwargs):
    kwargs['__kind__'] = 'serial'
    return kwargs


def load_config(filename):
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


SERVER = None


def run(options):
    global SERVER
    config = load_config(options.config)
    try:
        with Server(config) as server:
            SERVER = server
            server.run()
    except KeyboardInterrupt:  # pragma: no cover
        logging.info('Interrupted. Bailing out...')
    finally:
        SERVER = None


def main(args=None):
    parser = optparse.OptionParser()
    parser.add_option('-c', '--config', help='config file name')
    options, args = parser.parse_args(args)
    if options.config is None:
        parser.error('Missing configuration file argument (-c/--config)')
    run(options)


if __name__ == "__main__":
    main()  # pragma: no cover
