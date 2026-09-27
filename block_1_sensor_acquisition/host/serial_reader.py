"""Read MP01 sample packets from an ESP32 serial connection."""

from __future__ import annotations

from collections.abc import Iterator
from threading import Event
from typing import BinaryIO

from .packet_decoder import PacketDecoder, SignalChunk


def decode_stream(stream: BinaryIO, read_size: int = 4096) -> Iterator[SignalChunk]:
	"""Decode packets from any blocking binary stream, including a serial port."""
	if read_size <= 0:
		raise ValueError("read_size must be positive")
	decoder = PacketDecoder()
	while True:
		data = stream.read(read_size)
		if not data:
			return
		yield from decoder.feed(data)


def read_serial(
	port: str,
	baudrate: int = 921_600,
	timeout_s: float = 0.2,
	read_size: int = 4096,
	stop_event: Event | None = None,
) -> Iterator[SignalChunk]:
	"""Open a serial port and yield decoded sample chunks until it closes."""
	if baudrate <= 0:
		raise ValueError("baudrate must be positive")
	if timeout_s <= 0:
		raise ValueError("timeout_s must be positive")
	if read_size <= 0:
		raise ValueError("read_size must be positive")
	try:
		import serial
	except ImportError as exc:
		raise RuntimeError("serial capture requires pyserial; install it with pip install pyserial") from exc

	with serial.Serial(port, baudrate=baudrate, timeout=timeout_s) as connection:
		decoder = PacketDecoder()
		while connection.is_open and (stop_event is None or not stop_event.is_set()):
			data = connection.read(read_size)
			if data:
				yield from decoder.feed(data)
