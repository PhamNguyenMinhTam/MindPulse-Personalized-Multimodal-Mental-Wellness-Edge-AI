"""Binary packet framing shared by ESP32 firmware and the host collector."""

from __future__ import annotations

import struct
import uuid
import zlib
from dataclasses import dataclass
from enum import IntEnum


MAGIC = b"MP01"
PROTOCOL_VERSION = 1
HEADER = struct.Struct("<4sBBH16sIIQII")
CRC = struct.Struct("<I")
MAX_PAYLOAD_BYTES = 1_048_576


class Modality(IntEnum):
	VOICE = 1
	PPG = 2


@dataclass(frozen=True)
class SignalChunk:
	session_id: uuid.UUID
	modality: Modality
	sequence: int
	sample_rate_hz: int
	timestamp_start_us: int
	samples: tuple[int, ...] | tuple[tuple[int, int], ...]

	def __post_init__(self) -> None:
		if self.sample_rate_hz <= 0:
			raise ValueError("sample_rate_hz must be positive")
		if self.sequence < 0:
			raise ValueError("sequence must be non-negative")
		if self.timestamp_start_us < 0:
			raise ValueError("timestamp_start_us must be non-negative")
		if not self.samples:
			raise ValueError("a signal chunk must contain at least one sample")

	@property
	def sample_count(self) -> int:
		return len(self.samples)

	@property
	def timestamp_end_us(self) -> int:
		"""Exclusive end time, derived from count and rate on the device clock."""
		return self.timestamp_start_us + (
			self.sample_count * 1_000_000 + self.sample_rate_hz - 1
		) // self.sample_rate_hz


class PacketDecoder:
	"""Incrementally decode MP01 packets from an arbitrary byte stream."""

	def __init__(self, max_payload_bytes: int = MAX_PAYLOAD_BYTES) -> None:
		if max_payload_bytes <= 0:
			raise ValueError("max_payload_bytes must be positive")
		self._buffer = bytearray()
		self._max_payload_bytes = max_payload_bytes
		self.bad_packets = 0
		self.discarded_bytes = 0

	def feed(self, data: bytes) -> list[SignalChunk]:
		self._buffer.extend(data)
		decoded: list[SignalChunk] = []

		while True:
			magic_at = self._buffer.find(MAGIC)
			if magic_at < 0:
				keep = min(len(MAGIC) - 1, len(self._buffer))
				discard = len(self._buffer) - keep
				if discard:
					del self._buffer[:discard]
					self.discarded_bytes += discard
				break
			if magic_at:
				del self._buffer[:magic_at]
				self.discarded_bytes += magic_at
			if len(self._buffer) < HEADER.size:
				break

			fields = HEADER.unpack_from(self._buffer)
			magic, version, modality_value, _flags, session_bytes, sequence, rate, start_us, count, payload_size = fields
			if (
				magic != MAGIC
				or version != PROTOCOL_VERSION
				or rate == 0
				or count == 0
				or payload_size > self._max_payload_bytes
			):
				self._reject_frame()
				continue

			try:
				modality = Modality(modality_value)
			except ValueError:
				self._reject_frame()
				continue

			bytes_per_sample = 2 if modality is Modality.VOICE else 8
			if payload_size != count * bytes_per_sample:
				self._reject_frame()
				continue

			packet_size = HEADER.size + payload_size + CRC.size
			if len(self._buffer) < packet_size:
				break
			expected_crc = CRC.unpack_from(self._buffer, packet_size - CRC.size)[0]
			actual_crc = zlib.crc32(memoryview(self._buffer)[: packet_size - CRC.size])
			if expected_crc != actual_crc:
				self._reject_frame()
				continue

			payload_start = HEADER.size
			payload_end = payload_start + payload_size
			payload = self._buffer[payload_start:payload_end]
			if modality is Modality.VOICE:
				samples: tuple[int, ...] | tuple[tuple[int, int], ...] = struct.unpack(
					f"<{count}h", payload
				)
			else:
				flat = struct.unpack(f"<{count * 2}I", payload)
				samples = tuple((flat[i], flat[i + 1]) for i in range(0, len(flat), 2))

			decoded.append(
				SignalChunk(
					session_id=uuid.UUID(bytes=session_bytes),
					modality=modality,
					sequence=sequence,
					sample_rate_hz=rate,
					timestamp_start_us=start_us,
					samples=samples,
				)
			)
			del self._buffer[:packet_size]

		return decoded

	def _reject_frame(self) -> None:
		del self._buffer[0]
		self.bad_packets += 1
		self.discarded_bytes += 1


def encode_packet(chunk: SignalChunk) -> bytes:
	"""Encode a chunk using the same wire format as the ESP32 transport."""
	if chunk.modality is Modality.VOICE:
		payload = struct.pack(f"<{chunk.sample_count}h", *chunk.samples)
	else:
		flattened: list[int] = []
		for pair in chunk.samples:
			if not isinstance(pair, tuple) or len(pair) != 2:
				raise ValueError("PPG samples must be (red, infrared) pairs")
			flattened.extend(pair)
		payload = struct.pack(f"<{len(flattened)}I", *flattened)

	header = HEADER.pack(
		MAGIC,
		PROTOCOL_VERSION,
		int(chunk.modality),
		0,
		chunk.session_id.bytes,
		chunk.sequence,
		chunk.sample_rate_hz,
		chunk.timestamp_start_us,
		chunk.sample_count,
		len(payload),
	)
	packet = header + payload
	return packet + CRC.pack(zlib.crc32(packet))
