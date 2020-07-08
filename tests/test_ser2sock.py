import io
import os
import time
import errno
import socket
import threading
import urllib.request

import ser2sock.server

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
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.close()

    @property
    def serial_name(self):
        return os.ttyname(self.slave_fd)

    def handle_request(self):
        data = self.master.readline()
        assert data == REQUEST
        os.write(self.master_fd, REPLY)

    def close(self):
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master = None
            self.master_fd = None
        if self.slave_fd is not None:
            try:
                os.close(self.slave_fd)
            except OSError:
                pass
            self.slave_fd = None


def _server(template, tmp_path):
    assert ser2sock.server.SERVER is None

    cfg_filename = tmp_path / 'config.py'

    with Hardware() as hardware:
        with open(cfg_filename, "w") as cfg_file:
            cfg_text = template.format(serial=hardware.serial_name)
            cfg_file.write(cfg_text)
        th = threading.Thread(target=ser2sock.server.main, args=(['-c', cfg_filename],))
        th.daemon = True
        th.start()
        while ser2sock.server.SERVER is None:
            time.sleep(0.01)
        server = ser2sock.server.SERVER
        server.thread = th
        server.hardware = hardware
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
    assert ser2sock.server.SERVER is None
    cfg_filename = tmp_path / 'config_no_hw.py'
    with open(cfg_filename, "w") as cfg_file:
        cfg_file.write(CONFIG_TEMPLATE.format(serial='/dev/tty-void'))

    th = threading.Thread(target=ser2sock.server.main, args=(['-c', cfg_filename],))
    th.start()
    while ser2sock.server.SERVER is None:
        time.sleep(0.01)
    server = ser2sock.server.SERVER
    server.thread = th
    yield server
    server.stop()
    th.join()
    os.unlink(cfg_filename)


def test_load_config():
    config = ser2sock.server.load_config("config_one.py")
    bridges = [
        {
            'serial': dict(ser2sock.server.SERIAL_DEFAULTS, port="/dev/ttyS0"),
            'tcp': dict(ser2sock.server.TCP_DEFAULTS, address="0:0")
        }
    ]
    assert config["bridges"] == bridges


def test_web_server(web_server):
    _, port = web_server.bridges[0].sock.getsockname()
    with socket.create_connection(('localhost', port)) as client:
        client.sendall(REQUEST)
        web_server.hardware.handle_request()
        assert client.recv(1024) == REPLY
    _, web_port = web_server.web_server.web_server.socket.getsockname()
    with urllib.request.urlopen('http://localhost:{}/'.format(web_port)) as f:
        data = f.read().decode()
        assert data.startswith('<!doctype')
        assert web_server.hardware.serial_name in data

def test_server(server):
    _, port = server.bridges[0].sock.getsockname()
    with socket.create_connection(('localhost', port)) as client:
        client.sendall(REQUEST)
        server.hardware.handle_request()
        assert client.recv(1024) == REPLY


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
            server.hardware.handle_request()
            assert client.recv(1024) == REPLY
            server.hardware.close()
            client.sendall(b"*IDN?\n")
            assert not client.recv(1024)
            raise ConnectionResetError()


def test_server_no_client(server):
    _, port = server.bridges[0].sock.getsockname()
    with socket.create_connection(('localhost', port)) as client1:
        client1.sendall(REQUEST)
        server.hardware.handle_request()
        #client1.close()
        time.sleep(0.01)
    with socket.create_connection(('localhost', port)) as client2:
        client2.sendall(REQUEST)
        server.hardware.handle_request()
        assert client2.recv(1024) == REPLY


def test_server_missing_argument():
    with pytest.raises(SystemExit) as error:
        ser2sock.server.main([])
    assert error.value.code == 2


def test_2_clients_to_1_serial(server):
    _, port = server.bridges[0].sock.getsockname()
    with socket.create_connection(('localhost', port)) as client1:
        client1.sendall(REQUEST)
        server.hardware.handle_request()
        assert client1.recv(1024) == REPLY

        with pytest.raises(ConnectionResetError) as error:
            with socket.create_connection(('localhost', port)) as client2:
                client2.sendall(REQUEST)
                client2.recv(1024)
        assert error.value.errno == errno.ECONNRESET

    with socket.create_connection(('localhost', port)) as client3:
        client3.sendall(REQUEST)
        server.hardware.handle_request()
        assert client3.recv(1024) == REPLY


