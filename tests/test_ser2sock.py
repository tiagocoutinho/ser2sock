import io
import os
import socket

from ser2sock import Server, serial, tcp, load_config


def test_load_config():
    config = load_config("config_one.py")
    bridges = [
        [serial(address="/dev/ttyS0"), tcp(address=("0", 0))]
    ]
    assert config["bridges"] == bridges


def test_one_bridge():
    request = b"*IDN?\n"
    reply = b"ACME,road-runner,v1.245,58477272"

    master_fd, slave_fd = os.openpty()
    serial_name = os.ttyname(slave_fd)
    config = dict(bridges=[
        [serial(address=serial_name), tcp(address=("0", 0))]
    ])

    master = io.open(master_fd, "rb")

    def on_master_received(sl):
        assert sl is master
        data = sl.readline()
        assert data == request
        os.write(master_fd, reply)

    server = Server(config)
    assert not server.listener
    finished = [False]

    with server:
        # tcp
        assert len(server.listener) == 1
        server.add_reader(master, on_master_received)
        assert master in server.listener
        # tcp, master
        assert len(server.listener) == 2
        host, port = server.bridges[0].server.getsockname()
        with socket.create_connection(('localhost', port)) as client:
            assert len(server.listener) == 2
            server.step()
            # tcp, master, client (server end)
            assert len(server.listener) == 3

            def on_client_received(cl):
                try:
                    assert cl is client
                    assert cl.recv(1024) == reply
                finally:
                    finished[0] = True

            server.add_reader(client, on_client_received)
            assert client in server.listener
            # tcp, master, client (server), client (manual)
            assert len(server.listener) == 4
            client.sendall(request)
            assert len(server.listener) == 4
            server.step()
            # tcp, master, client (server), client (manual), serial
            assert len(server.listener) == 5

            while not finished[0]:
                server.step()
        # tcp, master, client (server), client (manual), serial
        assert len(server.listener) == 5
        server.remove_reader(client)
        # tcp, master, client (server), serial
        assert len(server.listener) == 4
        server.remove_reader(master)
        # tcp, client (server), serial
        assert len(server.listener) == 3
        server.step()
        # tcp
        assert len(server.listener) == 1

        os.close(master_fd)
        os.close(slave_fd)


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(message)s'
    )
    test_one_bridge()
