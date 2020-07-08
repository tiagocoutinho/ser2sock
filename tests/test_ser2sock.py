import io
import os
import time
import errno
import socket
import threading

import ser2sock
from ser2sock import Server, load_config, main

import pytest


CONFIG_TEMPLATE = """
bridges = [
    [serial(port="{serial}"), tcp(address=":0")]
]
"""


WEB_CONFIG_TEMPLATE = """
bridges = [
    [serial(port="{serial}"), tcp(address=":0")]
]
web = ":0"
"""


REQUEST = b"*IDN?\n"
REPLY = b"ACME,road-runner,v1.245,58477272"


class Hardware:

    commands = {
        REQUEST: REPLY
    }

    def __enter__(self):
        self.master_fd, self.slave_fd = os.openpty()
        self.master = io.open(self.master_fd, "rb")
        self.nb_requests = 0
        self.server = None
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.close()

    @property
    def serial_name(self):
        return os.ttyname(self.slave_fd)

    def on_request(self):
        self.nb_requests += 1
        request = self.master.readline()
        reply = self.commands.get(request)
        if reply:
            time.sleep(0.01)
            os.write(self.master_fd, reply)

    def register(self, server):
        server.add_reader(self.master_fd, self.on_request)

    def close(self):
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        if self.slave_fd is not None:
            try:
                os.close(self.slave_fd)
            except OSError:
                pass
            self.slave_fd = None


def _server(template, tmp_path):
    assert ser2sock.SERVER is None
    with Hardware() as hardware:
        cfg_filename = tmp_path / 'config.py'
        with open(cfg_filename, "w") as cfg_file:
            cfg_file.write(template.format(serial=hardware.serial_name))
        th = threading.Thread(target=ser2sock.main, args=(['-c', cfg_filename],))
        th.daemon = True
        th.start()
        while ser2sock.SERVER is None:
            time.sleep(0.01)
        server = ser2sock.SERVER
        server.thread = th
        server.hardware = hardware
        hardware.register(server)
        yield server
        server.stop()
        th.join()
        os.unlink(cfg_filename)


@pytest.fixture
def server(tmp_path):
    for i in _server(CONFIG_TEMPLATE, tmp_path):
        yield i


@pytest.fixture
def web_server(tmp_path):
    for i in _server(WEB_CONFIG_TEMPLATE, tmp_path):
        yield i


@pytest.fixture
def server_no_hw(tmp_path):
    assert ser2sock.SERVER is None
    cfg_filename = tmp_path / 'config_no_hw.py'
    with open(cfg_filename, "w") as cfg_file:
        cfg_file.write(CONFIG_TEMPLATE.format(serial='/dev/tty-void'))

    th = threading.Thread(target=ser2sock.main, args=(['-c', cfg_filename],))
    th.start()
    while ser2sock.SERVER is None:
        time.sleep(0.01)
    server = ser2sock.SERVER
    server.thread = th
    yield server
    server.stop()
    th.join()
    os.unlink(cfg_filename)


def test_load_config():
    config = load_config("config_one.py")
    bridges = [
        {
            'serial': dict(ser2sock.SERIAL_DEFAULTS, port="/dev/ttyS0"),
            'tcp': dict(ser2sock.TCP_DEFAULTS, address="0:0")
        }
    ]
    assert config["bridges"] == bridges


def test_web_server(web_server):
    _, port = web_server.bridges[0].sock.getsockname()
    with socket.create_connection(('localhost', port)) as client:
        client.sendall(REQUEST)
        assert client.recv(1024) == REPLY
        assert web_server.hardware.nb_requests == 1
    _, web_port = web_server.web_server.web_server.socket.getsockname()
    

def test_server(server):
    _, port = server.bridges[0].sock.getsockname()
    with socket.create_connection(('localhost', port)) as client:
        client.sendall(REQUEST)
        assert client.recv(1024) == REPLY
        assert server.hardware.nb_requests == 1


def test_server_no_serial(server_no_hw):
    _, port = server_no_hw.bridges[0].sock.getsockname()
    with pytest.raises(ConnectionResetError) as error:
        with socket.create_connection(('localhost', port)) as client:
            client.sendall(b"*IDN?\n")
            client.recv(1024)
    assert error.value.errno == errno.ECONNRESET


def test_server_serial_close_after_success(server):
    _, port = server.bridges[0].sock.getsockname()
    with pytest.raises(ConnectionResetError) as error:
        with socket.create_connection(('localhost', port)) as client:
            client.sendall(REQUEST)
            assert client.recv(1024) == REPLY
            assert server.hardware.nb_requests == 1
            server.hardware.close()
            client.sendall(b"*IDN?\n")
            client.recv(1024)


def test_server_no_client(server):
    _, port = server.bridges[0].sock.getsockname()
    with socket.create_connection(('localhost', port)) as client1:
        client1.sendall(REQUEST)
        time.sleep(0.01)
        client1.close()
    assert server.hardware.nb_requests == 1
    with socket.create_connection(('localhost', port)) as client2:
        client2.sendall(REQUEST)
        assert client2.recv(1024) == REPLY
    assert server.hardware.nb_requests == 2


def test_server_missing_argument():
    with pytest.raises(SystemExit) as error:
        ser2sock.main([])
    assert error.value.code == 2


def test_2_clients_to_1_serial(server):
    _, port = server.bridges[0].sock.getsockname()
    with socket.create_connection(('localhost', port)) as client1:
        client1.sendall(REQUEST)
        assert client1.recv(1024) == REPLY
        assert server.hardware.nb_requests == 1

        with pytest.raises(ConnectionResetError) as error:
            with socket.create_connection(('localhost', port)) as client2:
                client2.sendall(REQUEST)
                client2.recv(1024)
        assert error.value.errno == errno.ECONNRESET
        assert server.hardware.nb_requests == 1

    with socket.create_connection(('localhost', port)) as client3:
        client3.sendall(REQUEST)
        assert client3.recv(1024) == REPLY
        assert server.hardware.nb_requests == 2

