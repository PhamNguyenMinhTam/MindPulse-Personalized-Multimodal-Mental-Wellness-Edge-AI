"""Session assembly and timestamp-based multimodal window alignment."""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .packet_decoder import Modality, SignalChunk


@dataclass
class MeasurementSession:
	session_id: uuid.UUID
	device_id: str
	started_at_utc: str = field(
		default_factory=lambda: datetime.now(timezone.utc).isoformat()
	)
	metadata: dict[str, Any] = field(default_factory=dict)
	voice_chunks: list[SignalChunk] = field(default_factory=list)
	ppg_chunks: list[SignalChunk] = field(default_factory=list)

	def add_chunk(self, chunk: SignalChunk) -> None:
		if chunk.session_id != self.session_id:
			raise ValueError("chunk belongs to a different measurement session")

		chunks = self.voice_chunks if chunk.modality is Modality.VOICE else self.ppg_chunks
		if chunks:
			previous = chunks[-1]
			if chunk.sequence <= previous.sequence:
				raise ValueError("chunk sequence must increase within each modality")
			if chunk.timestamp_start_us < previous.timestamp_end_us:
				raise ValueError("chunks for one modality must not overlap")
			if chunk.sample_rate_hz != previous.sample_rate_hz:
				raise ValueError("sample rate cannot change within a session stream")
		chunks.append(chunk)

	@property
	def voice_sample_rate_hz(self) -> int | None:
		return self.voice_chunks[0].sample_rate_hz if self.voice_chunks else None

	@property
	def ppg_sample_rate_hz(self) -> int | None:
		return self.ppg_chunks[0].sample_rate_hz if self.ppg_chunks else None

	def aligned_windows(
		self,
		window_duration_s: float,
		minimum_coverage: float = 0.95,
	) -> Iterable["SynchronizedWindow"]:
		"""Yield time-aligned windows without resampling either modality."""
		if window_duration_s <= 0:
			raise ValueError("window_duration_s must be positive")
		if not 0 < minimum_coverage <= 1:
			raise ValueError("minimum_coverage must be in (0, 1]")
		if not self.voice_chunks or not self.ppg_chunks:
			return

		start_us = max(self.voice_chunks[0].timestamp_start_us, self.ppg_chunks[0].timestamp_start_us)
		end_us = min(self.voice_chunks[-1].timestamp_end_us, self.ppg_chunks[-1].timestamp_end_us)
		window_us = round(window_duration_s * 1_000_000)
		if end_us - start_us < window_us:
			return

		voice_rate = self.voice_sample_rate_hz
		ppg_rate = self.ppg_sample_rate_hz
		assert voice_rate is not None and ppg_rate is not None
		cursor_us = start_us
		while cursor_us + window_us <= end_us:
			window_end_us = cursor_us + window_us
			voice_samples = _samples_in_interval(self.voice_chunks, cursor_us, window_end_us)
			ppg_samples = _samples_in_interval(self.ppg_chunks, cursor_us, window_end_us)
			expected_voice = window_duration_s * voice_rate
			expected_ppg = window_duration_s * ppg_rate
			if (
				len(voice_samples) >= math.floor(expected_voice * minimum_coverage)
				and len(ppg_samples) >= math.floor(expected_ppg * minimum_coverage)
			):
				yield SynchronizedWindow(
					timestamp_start_us=cursor_us,
					timestamp_end_us=window_end_us,
					voice_sample_rate_hz=voice_rate,
					ppg_sample_rate_hz=ppg_rate,
					voice_samples=voice_samples,
					ppg_samples=ppg_samples,
				)
			cursor_us = window_end_us

	def to_dict(self) -> dict[str, Any]:
		return {
			"session_id": str(self.session_id),
			"device_id": self.device_id,
			"started_at_utc": self.started_at_utc,
			"metadata": self.metadata,
			"voice_sample_rate_hz": self.voice_sample_rate_hz,
			"ppg_sample_rate_hz": self.ppg_sample_rate_hz,
			"voice_chunks": [_chunk_to_dict(chunk) for chunk in self.voice_chunks],
			"ppg_chunks": [_chunk_to_dict(chunk) for chunk in self.ppg_chunks],
		}

	def save_json(self, path: str | Path) -> None:
		destination = Path(path)
		destination.parent.mkdir(parents=True, exist_ok=True)
		destination.write_text(
			json.dumps(self.to_dict(), separators=(",", ":")), encoding="utf-8"
		)


class SessionRecorder:
	"""Collect decoded packets into one session and persist its raw streams."""

	def __init__(self, device_id: str, metadata: dict[str, Any] | None = None) -> None:
		if not device_id:
			raise ValueError("device_id must not be empty")
		self.device_id = device_id
		self.metadata = metadata or {}
		self.session: MeasurementSession | None = None

	def add_chunk(self, chunk: SignalChunk) -> MeasurementSession:
		if self.session is None:
			self.session = MeasurementSession(
				session_id=chunk.session_id,
				device_id=self.device_id,
				metadata=dict(self.metadata),
			)
		self.session.add_chunk(chunk)
		return self.session

	def save_json(self, path: str | Path) -> None:
		if self.session is None:
			raise ValueError("cannot save an empty measurement session")
		self.session.save_json(path)


@dataclass(frozen=True)
class SynchronizedWindow:
	timestamp_start_us: int
	timestamp_end_us: int
	voice_sample_rate_hz: int
	ppg_sample_rate_hz: int
	voice_samples: tuple[int, ...]
	ppg_samples: tuple[tuple[int, int], ...]


def _samples_in_interval(
	chunks: list[SignalChunk], start_us: int, end_us: int
) -> tuple[Any, ...]:
	selected: list[Any] = []
	for chunk in chunks:
		if chunk.timestamp_end_us <= start_us:
			continue
		if chunk.timestamp_start_us >= end_us:
			break
		first = max(0, _ceil_sample_index(start_us - chunk.timestamp_start_us, chunk.sample_rate_hz))
		last = min(
			chunk.sample_count,
			_ceil_sample_index(end_us - chunk.timestamp_start_us, chunk.sample_rate_hz),
		)
		if first < last:
			selected.extend(chunk.samples[first:last])
	return tuple(selected)


def _ceil_sample_index(delta_us: int, sample_rate_hz: int) -> int:
	if delta_us <= 0:
		return 0
	return (delta_us * sample_rate_hz + 999_999) // 1_000_000


def _chunk_to_dict(chunk: SignalChunk) -> dict[str, Any]:
	return {
		"sequence": chunk.sequence,
		"sample_rate_hz": chunk.sample_rate_hz,
		"timestamp_start_us": chunk.timestamp_start_us,
		"timestamp_end_us": chunk.timestamp_end_us,
		"samples": chunk.samples,
	}
