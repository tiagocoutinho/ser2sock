import os
import sys
import runpy
import socket
import select
import logging
import datetime
import optparse
import contextlib

PY2 = sys.version_info[0] == 2

if PY2:
    import selectors2 as selectors  # pragma: no cover
else:
    import selectors

import serial


__version__ = "4.0.0"

IPTOS_NORMAL = 0x0
IPTOS_LOWDELAY = 0x10
IPTOS_THROUGHPUT = 0x08
IPTOS_RELIABILITY = 0x04
IPTOS_MINCOST = 0x02


def setsockopt(sock, reuse_addr=None, no_delay=None, tos=None):
    if reuse_addr is not None:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 if reuse_addr else 0)
    if no_delay is not None and hasattr(socket, "TCP_NODELAY"):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1 if no_delay else 0)
    if tos is not None and hasattr(socket, "IP_TOS"):
        sock.setsockopt(socket.SOL_IP, socket.IP_TOS, tos)


def create_server(
    address, reuse_addr=True, no_delay=True, tos=IPTOS_LOWDELAY, listen=1):
    server = socket.socket()
    host, port = _tcp_host_port(address)
    setsockopt(server, reuse_addr=reuse_addr, no_delay=no_delay, tos=tos)
    server.bind((host, port))
    server.listen(listen)
    server.setblocking(False)
    return server


def create_serial(config):
    config = dict(config)
    port = config.pop('port')
    ser = serial.Serial(**config)
    ser.port = port
    return ser


class Bridge:

    def __init__(self, config, server):
        self.config = config
        self.server = server
        self.sock = None
        self.client = None
        self.client_bytes = 0
        self.client_ts = None
        self.client_nb = 0
        self.serial = create_serial(config['serial'])
        self.serial_bytes = 0
        self.ensure_server()

    def ensure_serial(self):
        if self.serial.isOpen():
            return
        self.serial.open()
        self.server.add_reader(self.serial, self.serial_to_tcp)

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
        if self.serial.isOpen():
            self.server.remove_reader(self.serial)
            self.serial.close()

    def close_server(self):
        if self.sock:
            self.server.remove_reader(self.sock)
            self.sock.close()
            self.sock = None

    def tcp_to_serial(self):
        try:
            self._tcp_to_serial()
        except Exception as error:
            logging.error('error tcp -> serial: %r', error)
            self.close_serial()
            self.close_client()

    def _tcp_to_serial(self):
        data = self.client.recv(1024)
        if data:
            logging.debug('tcp -> serial: %r', data)
            self.serial.write(data)
            self.client_bytes += len(data)
        else:
            logging.info('connection closed')
            self.close_serial()
            self.close_client()

    def serial_to_tcp(self):
        try:
            self._serial_to_tcp()
        except Exception as error:
            logging.error('error reading from serial %r', error)
            self.close_client()
            self.close_serial()
            return

    def _serial_to_tcp(self):
        data = self.serial.read(self.serial.inWaiting())
        if self.client is None:
            logging.info('serial data discarded (no client): %r', data)
        else:
            logging.debug('serial -> tcp: %r', data)
            self.client.sendall(data)
            self.serial_bytes += len(data)

    def close(self):
        self.close_client()
        self.close_serial()
        self.close_server()

    def accept(self):
        opts = self.config['tcp']
        client, addr = self.sock.accept()
        setsockopt(client, no_delay=opts['no_delay'], tos=opts['tos'])
        self.client_nb += 1
        self.client_ts = datetime.datetime.now()
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

    def reconfig(self, config):
        if self.config == config:
            name = self.config['serial']['port']
            logging.info('reconfig %r: no changes, so skip it', name)
            return
        old_ser, new_ser = self.config['serial'], config['serial']
        if old_ser != new_ser:
            if old_ser['port'] != new_ser['port']:
                self.close_serial()
            for key, value in new_ser.items():
                old_value = old_ser[key]
                if value != old_value:
                    logging.info('setting %r %r from %r to %r', old_ser['port'],
                                 key, old_value, value)
                    setattr(self.serial, key, value)
        old_tcp, new_tcp = self.config['tcp'], config['tcp']
        if old_tcp != new_tcp:
            if old_tcp['address'] != new_tcp['address']:
                self.close_client()
                self.close_server()
                self.config = config
                self.ensure_server()
            else:
                # other tcp options changed
                opts = dict(no_delay=new_tcp['no_delay'], tos=new_tcp['tos'])
                if self.client:
                    setsockopt(self.client, **opts)
                if self.server:
                    setsockopt(self.server, **opts)
        self.config = config


def make_bridge(config, server):
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
        self.close()

    def close(self):
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
        for bridge, config in zip(self.bridges, config['bridges']):
            bridge.reconfig(config)


def _tcp(**kwargs):
    kwargs['__kind__'] = 'tcp'
    return kwargs


def _serial(**kwargs):
    kwargs['__kind__'] = 'serial'
    return kwargs


def _tcp_host_port(addr):
    if isinstance(addr, str):
        host, port = addr.rsplit(":", 1)
        addr = "0" if not host else host, int(port)
    return addr


def _human_size(n):
    for i in ' kMGTPEZY':
        if n / 1000 < 1:
            break
        n /= 1000
    return n, i


TCP_DEFAULTS = {
    'reuse_addr': True,
    'no_delay': True,
    'tos': IPTOS_LOWDELAY,
    'listen': 1
}


SERIAL_DEFAULTS = {
    'baudrate': 9600,
    'bytesize': serial.EIGHTBITS,
    'parity': serial.PARITY_NONE,
    'stopbits': serial.STOPBITS_ONE
}

def _to_tcp_address(addr):
    if isinstance(addr, str):
        host, port = addr.rsplit(":", 1)
        addr = "0" if not host else host, port
    return "{0}:{1}".format(*addr)


def _to_tcp(cfg):
    result = dict(TCP_DEFAULTS, **cfg)
    result['address'] = _to_tcp_address(cfg['address'])
    return result


def _to_serial(cfg):
    return dict(SERIAL_DEFAULTS, **cfg)


def _to_bridge(cfg):
    if isinstance(cfg, (tuple, list)):
        a, b = cfg
        serial, tcp = (a, b) if a.pop('__kind__') == 'serial' else (b, a)
        b.pop('__kind__')
        cfg = dict(serial=serial, tcp=tcp)
    cfg['tcp'] = _to_tcp(cfg['tcp'])
    cfg['serial'] = _to_serial(cfg['serial'])
    return cfg


def sanitize_config(config):
    return dict(
        bridges=[_to_bridge(bridge) for bridge in config.get('bridges', ())],
        web=_to_tcp_address(config['web']) if 'web' in config else None
    )


def load_config(filename):
    glob = dict(serial=_serial, tcp=_tcp)
    full = os.path.abspath(filename)
    path, fname = os.path.split(filename)
    mod_name, _ = os.path.splitext(fname)
    sys.path.insert(0, path)
    try:
        config = runpy.run_module(mod_name, glob)
    finally:
        sys.path.pop(0)
    return sanitize_config(config)


def web_run(server, config):
    import bottle
    import wsgiref.simple_server

    bottle.TEMPLATE_PATH += [os.path.dirname(__file__)]

    host, port = _tcp_host_port(config["web"])

    app = bottle.Bottle()

    def form_to_config(form):
        bridges = {}
        for key, value in form.items():
            domain, name, index = key.split("-")
            index = int(index)
            if name in ("baudrate", "bytesize"):
                value = int(value)
            if name == "stopbits":
                try:
                    value = int(value)
                except ValueError:
                    assert value == "1.5"
                    value = float(value)
            bridge = bridges.setdefault(index, {})
            bridge.setdefault(domain, {})[name] = value
        bridges = [_to_bridge(bridges[index]) for index in sorted(bridges)]
        return dict(bridges=bridges)

    @app.get("/")
    def index():
        return bottle.template(
            'index.tpl', server=server, hostname=socket.gethostname(),
            baudrates=serial.Serial.BAUDRATES, human_size=_human_size
        )

    @app.post("/")
    def apply():
        new_config = form_to_config(bottle.request.forms)
        server.reconfig(new_config)
        return bottle.redirect("/")

    class WebServer(bottle.ServerAdapter):

        def run(self, app):  # pragma: no cover
            self.web_server = wsgiref.simple_server.make_server(self.host, self.port, app)
            sock = self.web_server.socket
            sock.setblocking(False)
            server.add_reader(sock, self.web_server.handle_request)
            server.run()

    web_server = WebServer(host, port)
    server.web_server = web_server
    bottle.run(app, server=web_server)


SERVER = None


def run(options):
    global SERVER
    config = load_config(options.config)
    try:
        with Server(config) as server:
            SERVER = server
            if config['web']:
                web_run(server, config)
            else:
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
