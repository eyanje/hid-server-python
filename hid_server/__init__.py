from __future__ import annotations
from pathlib import Path
from socket import socket, AF_UNIX, SOCK_SEQPACKET, SOCK_DGRAM
from itertools import chain

class BluetoothAddress:
    def __init__(self, bytes):
        self.bytes = bytes

    def __str__(self):
        return ':'.join('{:02X}'.format(b) for b in self.bytes)

    def __repr__(self):
        return str(self)

    def path_name(self):
        return '_'.join('{:02X}'.format(b) for b in self.bytes)

    @staticmethod
    def from_bytes(bs) -> BluetoothAddress:
        return BluetoothAddress(bytes(bs))

    @staticmethod
    def from_string(address) -> BluetoothAddress:
        bs = [int(a, 16) for a in address.split(':')]
        return BluetoothAddress(bytes(bs))

class Server:
    def __init__(self, root_directory=Path('/run/hid-server')):
        self.root_directory = Path(root_directory)

    def command_socket(self):
        path = self.root_directory / 'command'
        sock = CommandSocket()
        sock.connect(bytes(path))
        return sock

    def event_socket(self):
        path = self.root_directory / 'event'
        sock = EventSocket()
        sock.connect(bytes(path))
        return sock

    def device(self, address: BluetoothAddress):
        name = address.path_name()
        path = self.root_directory / name
        return HSDevice(path)

class CommandResult:
    pass

class CommandSocket(socket):
    def __init__(self, bufsize=1024):
        super().__init__(AF_UNIX, SOCK_SEQPACKET)
        self.bufsize = bufsize

    def __interpret_result(result):
        if result == r'\x00':
            return 'ok'
        elif result == r'\x01':
            return 'malformed'
        elif result == r'\x02':
            return 'disconnected'
        elif result == r'\x03':
            return 'refused'

    def up(self, sdp_record: bytes):
        """Advertise on the server using the given XML SDP record"""
        self.send(bytes(chain([1], sdp_record)))
        reply = self.recv(self.bufsize)
        return CommandSocket.__interpret_result(reply)

    def down(self):
        """Stop advertising"""
        self.send(b'\x02')
        reply = self.recv(self.bufsize)
        return CommandSocket.__interpret_result(reply)

class Event:
    LAGGED = 0x01
    CONTROL_LISTENING = 0x02
    INTERRUPT_LISTENING = 0x03
    DISCONNECTED = 0x04

    def __init__(self, event, data):
        self.event = event
        self.data = data

class EventSocket(socket):
    def __init__(self):
        super().__init__(AF_UNIX, SOCK_SEQPACKET)

    def read_event(self, bufsize=1024):
        """Read a single event"""
        buf = self.recv(bufsize)

        if len(buf) < 1:
            raise Error("Empty event")

        return Event(buf[0], buf[1:])


class Device:
    def __init__(self, base_path):
        self.base_path = base_path
        self._control_socket = None

    def close(self):
        if self._control_socket is not None:
            self._control_socket.close()

    def control_socket(self):
        if self._control_socket is not None:
            return self._control_socket

        self._control_socket = socket(AF_UNIX, SOCK_SEQPACKET)
        self._control_socket.connect(bytes(self.base_path / 'control'))
        return self._control_socket

    def interrupt_socket(self):
        sock = socket(AF_UNIX, SOCK_DGRAM)
        sock.connect(bytes(self.base_path / 'interrupt'))
        return sock
