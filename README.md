# ser2sock

![Pypi version][pypi]

A single-threaded, multi serial line to TCP bridge server.

Can run under python 2.6 up to 3.x (tested 3.8).

## Installation

From within your favorite python environment:

```console
pip install ser2sock
```

## Usage

```console
ser2net -c <configuration file>
```

### Configuration

In order to provide flexibility, configuration is written in python.

The only requirement is to have a `bridges` member which consists of a
sequence of bridges. A bridge is a dictionary with mandatory keys `serial`
and `tcp`.

Example:

```python

bridges = [
    {
        'serial': {'address': '/dev/ttyS0'},
        'tcp': {'address': ("0", 18500)}
    },
    {
        'serial': {'address': '/dev/ttyS1', 'baudrate': 19200},
        'tcp': {'address': ("0", 18501), 'no_delay': False}
    }
]
```

* `serial`: `address` mandatory. Supports any keyword supported by
  `serial.serial_for_url` (or `serial.Serial` if `serial_for_url` does not
  exist
* `tcp`: `address` mandatory (must be a pair bind host and port).
  * `reuse_addr`: (default: True) TCP reuse address
  * `no_delay`: (default: True) disable Nagle's algorithm
  * `tos`: (default: `0x10`, meaning low delay) type of service.

`tcp` and `serial` helpers are automatically loaded to the config namespace.
Here is the equivalent above config using helpers:

```python

bridges = [
    [serial(address="/dev/ttyS0"), tcp(address=("0", 18500))],
    [serial(address="/dev/ttyS1", baudrate=19200),
     tcp(address=("0", 18501), no_delay=False)],
]
```

You are free to put any code in your python configuration file.
Here is an example setting up logging:

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s'
)

bridges = [
    [serial(address="/dev/ttyS0"), tcp(address=("0", 18500))],
    [serial(address="/dev/ttyS1", baudrate=19200),
     tcp(address=("0", 18501), no_delay=False)],
]


```

## Web UI

The active configuration can be changed online through a web UI.

To enable web you need to install the extra package:

```console
$ pip install ser2sock[web]
```

...and enable the web app in the configuration with:

```python
bridges = [...]

web = ':8000'
```

ser2sock should now be visible [here](http://localhost:8000).

You should see something like this:

![web screenshot](web_screenshot.png)

Note that changes made with the web interface only affect the
active ser2sock instance and never the original configuration file.


That's all folks!

[pypi]: https://img.shields.io/pypi/pyversions/ser2sock.svg
