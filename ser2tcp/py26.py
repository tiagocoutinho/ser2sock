import socket
import select
import logging

import serial


def Serial(address='/tmp/dcp3000-1'):
    return serial.Serial(
        address, baudrate=19200, bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
        xonxoff=False, rtscts=False, timeout=1)


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s'
)


logging.info('Bootstraping bridge...')
server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0', 8500))
server.listen(1)
sources = set([server])
client = None
sl = None

logging.info('Ready to accept requests')
while True:
    readers, _, _ = select.select(sources, (), ())
    for reader in readers:
        if reader is server:
            cli, addr = reader.accept()
            logging.info('new connection from %r', addr)
            if client is None:
                client = cli
                sources.add(client)
            else:
                logging.warning('close new connection: already connected')
                cli.close()
        elif reader is client:
             data = reader.recv(4096)
             if not data:
                 logging.info('client disconnected')
                 sources.remove(reader)
                 client = None
                 if sl is not None:
                     sources.remove(sl)
                     sl.close()
                     sl = None
             else:
                 if sl is None:
                     sl = Serial()
                     sources.add(sl)
                 logging.debug('sock => serial: %r', data)
                 sl.write(data)
        elif reader is sl:
            #data = sl.read(sl.inWaiting())
            data = sl.readline()
            if client is not None:
                logging.debug('serial => sock: %r', data)
                client.sendall(data)
            else:
                logging.info('serial data discarded (no client): %r', data)
        else:
            logging.error('unexpected fd!')
