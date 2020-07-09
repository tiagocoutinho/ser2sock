import socket

import serial

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
    address, reuse_addr=True, no_delay=True, tos=IPTOS_LOWDELAY, listen=1
):
    server = socket.socket()
    setsockopt(server, reuse_addr=reuse_addr, no_delay=no_delay, tos=tos)
    server.bind(address)
    server.listen(listen)
    server.setblocking(False)
    return server


def create_serial(config):
    config = dict(config)
    port = config.pop("port")
    ser = serial.Serial(**config)
    ser.port = port
    return ser
