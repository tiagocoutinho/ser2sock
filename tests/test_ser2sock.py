import io
import os
import time
import errno
import socket
import threading

import ser2sock
from ser2sock import Server, serial, tcp, load_config, main

import pytest


CONFIG_TEMPLATE = """
bridges = [
    [serial(address="{serial}"), tcp(address=("0", 0))]
]
"""

class Hardware:

    commands = {
        b'*IDN?\n': b"ACME,road-runner,v1.245,58477272"
    }

    def __enter__(self):
        self.master_fd, self.slave_fd = os.openpty()
        self.master = io.open(self.master_fd, "rb")
        self.nb_requests = 0
        return self

    def __exit__(self, exc_type, exc_value, tb):
        os.close(self.master_fd)
        os.close(self.slave_fd)

    @property
    def serial_name(self):
        return os.ttyname(self.slave_fd)

    def on_request(self, fobj):
        assert fobj is self.master
        self.nb_requests += 1
        request = fobj.readline()
        reply = self.commands.get(request)
        if reply:
            os.write(self.master_fd, reply)

    def register(self, server):
        server.add_reader(self.master, self.on_request)

    def unregister(self, server):
        server.remove_reader(self.master)


@pytest.fixture
def server(tmp_path):
    with Hardware() as hardware:
        cfg_filename = tmp_path / 'config.py'
        with open(cfg_filename, "w") as cfg_file:
            cfg_file.write(CONFIG_TEMPLATE.format(serial=hardware.serial_name))

        th = threading.Thread(target=ser2sock.main, args=(['-c', cfg_filename],))
        th.start()
        while ser2sock.SERVER is None:
            time.sleep(0.01)
        server = ser2sock.SERVER
        server.thread = th
        server.hardware = hardware
        hardware.register(server)
        yield server
        hardware.unregister(server)
        server.stop()
        th.join()
        os.unlink(cfg_filename)


def test_load_config():
    config = load_config("config_one.py")
    bridges = [
        [serial(address="/dev/ttyS0"), tcp(address=("0", 0))]
    ]
    assert config["bridges"] == bridges


def test_one_bridge():
    request = b"*IDN?\n"
    reply = b"ACME,road-runner,v1.245,58477272"

    with Hardware() as hardware:
        config = dict(bridges=[
            [serial(address=hardware.serial_name), tcp(address=("0", 0))]
        ])

        server = Server(config)
        assert not server.listener
        finished = [False]

        with server:
            # internal channel, tcp
            assert len(server.listener) == 2
            hardware.register(server)
            assert hardware.master in server.listener
            # internal channel, tcp, master
            assert len(server.listener) == 3
            host, port = server.bridges[0].sock.getsockname()
            with socket.create_connection(('localhost', port)) as client:
                assert len(server.listener) == 3
                server.step()
                # internal channel, tcp, master, client (server end)
                assert len(server.listener) == 4

                def on_client_received(cl):
                    try:
                        assert cl is client
                        assert cl.recv(1024) == reply
                    finally:
                        finished[0] = True

                server.add_reader(client, on_client_received)
                assert client in server.listener
                # internal channel, tcp, master, client (server), client (manual)
                assert len(server.listener) == 5
                client.sendall(request)
                assert len(server.listener) == 5
                server.step()
                # internal channel, tcp, master, client (server), client (manual), serial
                assert len(server.listener) == 6

                while not finished[0]:
                    server.step()

                assert hardware.nb_requests == 1

            # internal channel, tcp, master, client (server), client (manual), serial
            assert len(server.listener) == 6
            server.remove_reader(client)
            # internal channel, tcp, master, client (server), serial
            assert len(server.listener) == 5
            hardware.unregister(server)
            # internal channel, tcp, client (server), serial
            assert len(server.listener) == 4
            server.step()
            # internal channel, tcp
            assert len(server.listener) == 2
        assert not len(server.listener)


def test_server(server):
    _, port = server.bridges[0].sock.getsockname()
    with socket.create_connection(('localhost', port)) as client:
        request = b"*IDN?\n"
        reply = b"ACME,road-runner,v1.245,58477272"
        client.sendall(request)
        assert client.recv(1024) == reply
        assert server.hardware.nb_requests == 1


def test_server_missing_argument(server):
    with pytest.raises(SystemExit) as error:
        ser2sock.main([])
    assert error.value.code == 2


def test_2_clients_to_1_serial(server):
    _, port = server.bridges[0].sock.getsockname()
    with socket.create_connection(('localhost', port)) as client1:
        request = b"*IDN?\n"
        reply = b"ACME,road-runner,v1.245,58477272"
        client1.sendall(request)
        assert client1.recv(1024) == reply
        assert server.hardware.nb_requests == 1

        with pytest.raises(ConnectionResetError) as error:
            with socket.create_connection(('localhost', port)) as client2:
                client2.sendall(b'bla\n')
                client2.recv(100)
        assert error.value.errno == errno.ECONNRESET
        assert server.hardware.nb_requests == 1

    with socket.create_connection(('localhost', port)) as client3:
        request = b"*IDN?\n"
        reply = b"ACME,road-runner,v1.245,58477272"
        client3.sendall(request)
        assert client3.recv(1024) == reply
        assert server.hardware.nb_requests == 2

