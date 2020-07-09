import os
import sys
import runpy

import serial


TCP_DEFAULTS = {
    "reuse_addr": True,
    "no_delay": True,
    "tos": 0x10,
    "listen": 1,
}


SERIAL_DEFAULTS = {
    "baudrate": 9600,
    "bytesize": serial.EIGHTBITS,
    "parity": serial.PARITY_NONE,
    "stopbits": serial.STOPBITS_ONE,
}


def tcp_config(**kwargs):
    kwargs["__kind__"] = "tcp"
    return kwargs


def serial_config(**kwargs):
    kwargs["__kind__"] = "serial"
    return kwargs


def tcp_host_port(addr):
    if isinstance(addr, str):
        host, port = addr.rsplit(":", 1)
        addr = "0" if not host else host, int(port)
    return addr


def to_tcp_address(addr):
    if isinstance(addr, str):
        host, port = addr.rsplit(":", 1)
        addr = "0" if not host else host, port
    return "{0}:{1}".format(*addr)


def to_tcp(cfg):
    result = dict(TCP_DEFAULTS, **cfg)
    result["address"] = to_tcp_address(cfg["address"])
    return result


def to_serial(cfg):
    return dict(SERIAL_DEFAULTS, **cfg)


def to_bridge(cfg):
    if isinstance(cfg, (tuple, list)):
        a, b = cfg
        serial, tcp = (a, b) if a.pop("__kind__") == "serial" else (b, a)
        b.pop("__kind__")
        cfg = dict(serial=serial, tcp=tcp)
    cfg["tcp"] = to_tcp(cfg["tcp"])
    cfg["serial"] = to_serial(cfg["serial"])
    return cfg


def sanitize_config(config):
    return dict(
        bridges=[to_bridge(bridge) for bridge in config.get("bridges", ())],
        web=to_tcp_address(config["web"]) if "web" in config else None,
    )


def load_config(filename):
    glob = dict(serial=serial_config, tcp=tcp_config)
    full = os.path.abspath(filename)
    path, fname = os.path.split(filename)
    mod_name, _ = os.path.splitext(fname)
    sys.path.insert(0, path)
    try:
        config = runpy.run_module(mod_name, glob)
    finally:
        sys.path.pop(0)
    return sanitize_config(config)


def human_size(n):
    for i in " kMGTPEZY":
        if n / 1000 < 1:
            break
        n /= 1000
    return n, i
