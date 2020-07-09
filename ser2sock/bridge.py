import socket
import logging
import datetime

import serial

from .config import tcp_host_port
from .comm import create_serial, create_server, setsockopt


class Bridge:
    def __init__(self, config, server):
        self.config = config
        self.server = server
        self.sock = None
        self.client = None
        self.client_bytes = 0
        self.client_ts = None
        self.client_nb = 0
        self.serial = create_serial(config["serial"])
        self.serial_bytes = 0
        self.ensure_server()

    def ensure_serial(self):
        if self.serial.isOpen():
            return
        self.serial.open()
        self.server.add_reader(self.serial, self.serial_to_tcp)

    def ensure_server(self):
        if self.sock is None:
            tcp = dict(self.config["tcp"])
            tcp["address"] = tcp_host_port(tcp.pop("address"))
            self.sock = create_server(**tcp)
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
            logging.error("error tcp -> serial: %r", error)
            self.close_serial()
            self.close_client()

    def _tcp_to_serial(self):
        data = self.client.recv(1024)
        if data:
            logging.debug("tcp -> serial: %r", data)
            self.serial.write(data)
            self.client_bytes += len(data)
        else:
            logging.info("connection closed")
            self.close_serial()
            self.close_client()

    def serial_to_tcp(self):
        try:
            self._serial_to_tcp()
        except Exception as error:
            logging.error("error reading from serial %r", error)
            self.close_client()
            self.close_serial()
            return

    def _serial_to_tcp(self):
        data = self.serial.read(self.serial.inWaiting())
        if self.client is None:
            logging.info("serial data discarded (no client): %r", data)
        else:
            logging.debug("serial -> tcp: %r", data)
            self.client.sendall(data)
            self.serial_bytes += len(data)

    def close(self):
        self.close_client()
        self.close_serial()
        self.close_server()

    def accept(self):
        opts = self.config["tcp"]
        client, addr = self.sock.accept()
        setsockopt(client, no_delay=opts["no_delay"], tos=opts["tos"])
        self.client_nb += 1
        self.client_ts = datetime.datetime.now()
        if self.client is None:
            logging.info("new connection from %r", addr)
            try:
                serial = self.ensure_serial()
            except Exception as error:
                logging.error("error openning serial port %r", error)
                client.close()
                return
            self.client = client
            self.client.setblocking(False)
            self.server.add_reader(client, self.tcp_to_serial)
        else:
            logging.info("disconnect client %r (already connected)", addr)
            client.close()

    def reconfig(self, config):
        if self.config == config:
            name = self.config["serial"]["port"]
            logging.info("reconfig %r: no changes, so skip it", name)
            return
        old_ser, new_ser = self.config["serial"], config["serial"]
        if old_ser != new_ser:
            if old_ser["port"] != new_ser["port"]:
                self.close_serial()
            for key, value in new_ser.items():
                old_value = old_ser[key]
                if value != old_value:
                    logging.info(
                        "setting %r %r from %r to %r",
                        old_ser["port"],
                        key,
                        old_value,
                        value,
                    )
                    setattr(self.serial, key, value)
        old_tcp, new_tcp = self.config["tcp"], config["tcp"]
        if old_tcp != new_tcp:
            if old_tcp["address"] != new_tcp["address"]:
                self.close_client()
                self.close_server()
                self.config = config
                self.ensure_server()
            else:
                # other tcp options changed
                opts = dict(no_delay=new_tcp["no_delay"], tos=new_tcp["tos"])
                if self.client:
                    setsockopt(self.client, **opts)
                if self.server:
                    setsockopt(self.server, **opts)
        self.config = config
