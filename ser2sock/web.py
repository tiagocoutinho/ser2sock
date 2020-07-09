import os
import socket

import serial
import bottle
import wsgiref.simple_server

from .config import tcp_host_port, human_size


def run(server, config):
    this_dir = os.path.dirname(__file__)

    bottle.TEMPLATE_PATH += [this_dir]

    host, port = tcp_host_port(config["web"])

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
        bridges = [to_bridge(bridges[index]) for index in sorted(bridges)]
        return dict(bridges=bridges)

    @app.get("/")
    def index():
        return bottle.template(
            "index.tpl",
            server=server,
            hostname=socket.gethostname(),
            baudrates=serial.Serial.BAUDRATES,
            human_size=human_size,
        )

    @app.post("/")
    def apply():
        new_config = form_to_config(bottle.request.forms)
        server.reconfig(new_config)
        return bottle.redirect("/")

    @app.route("/static/<filename>")
    def static(filename):
        return bottle.static_file(filename, root=this_dir)

    class WebServer(bottle.ServerAdapter):
        def run(self, app):  # pragma: no cover
            self.web_server = wsgiref.simple_server.make_server(
                self.host, self.port, app
            )
            sock = self.web_server.socket
            sock.setblocking(False)
            server.add_reader(sock, self.web_server.handle_request)
            server.run()

    web_server = WebServer(host, port)
    server.web_server = web_server
    bottle.run(app, server=web_server)
