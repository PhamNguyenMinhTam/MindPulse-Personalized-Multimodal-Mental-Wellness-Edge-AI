"""Canonical data models shared across MindPulse processing layers."""

from __future__ import annotations

import math
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from numbers import Real
from typing import ClassVar, TypedDict


class Modality(str, Enum):
	"""Supported signal categories, independent of the producing device."""

	VOICE = "voice"
	PHYSIOLOGICAL = "physiological"


class SignalUnit(str, Enum):
	"""Controlled semantic descriptions of canonical payload values."""

	RAW_COUNT = "raw_count"
	NORMALIZED_AMPLITUDE = "normalized_amplitude"
	ARBITRARY_UNIT = "arbitrary_unit"


class DeviceStatus(str, Enum):
	"""Generic operational state, independent of any producer or hardware."""

	READY = "ready"
	STREAMING = "streaming"
	DEGRADED = "degraded"
	RECONNECTING = "reconnecting"
	ERROR = "error"


class ContractVersionError(ValueError):
	"""Raised when a packet uses an unsupported Device Data Contract version."""


class CanonicalSignalCandidate(TypedDict):
	"""Canonical field shape emitted before contract validation.

	Keeping this candidate shape separate makes the pipeline's validation gate
	explicit without duplicating the canonical signal representation.
	"""

	modality: Modality
	sample_rate: float
	unit: SignalUnit
	payload: Sequence[Real]


@dataclass(frozen=True)
class CanonicalSignal:
	"""Validated one-dimensional waveform independent of producer format.

	``sample_rate`` is in Hz and must be finite and positive. ``payload`` is a
	non-empty sequence of finite numeric samples, normalized to an immutable
	tuple of floats. This contract cannot establish whether a producer's
	reported rate or unit is physically truthful, and it performs no DSP.
	"""

	modality: Modality
	sample_rate: float
	unit: SignalUnit
	payload: Sequence[Real]

	def __post_init__(self) -> None:
		"""Validate all canonical invariants and normalize enum/sample types."""
		object.__setattr__(self, "modality", _coerce_enum(self.modality, Modality, "modality"))
		object.__setattr__(self, "unit", _coerce_enum(self.unit, SignalUnit, "unit"))

		sample_rate = _finite_number(self.sample_rate, "sample_rate")
		if sample_rate <= 0:
			raise ValueError("sample_rate must be greater than 0 Hz")
		object.__setattr__(self, "sample_rate", sample_rate)

		if isinstance(self.payload, (str, bytes)) or not isinstance(self.payload, Sequence):
			raise TypeError("payload must be a sequence of numeric samples")
		if not self.payload:
			raise ValueError("payload must contain at least one sample")

		samples = tuple(_finite_number(value, f"payload[{index}]") for index, value in enumerate(self.payload))
		object.__setattr__(self, "payload", samples)


@dataclass(frozen=True)
class DevicePacket(CanonicalSignal):
	"""Versioned device envelope plus the existing canonical waveform fields.

	``device_id`` and ``session_id`` are opaque non-empty provenance labels.
	``sequence_id`` is a non-negative ordering value within a producer-defined
	stream/session scope; it does not trigger loss or ordering recovery.
``timestamp`` is an RFC 3339 UTC instant claimed to be the first sample's
	capture time. Validation checks representation only, not clock accuracy.
``signal_quality`` is an optional producer/estimator score in [0, 1]; it does
	not define or imply a quality algorithm. ``sample_count`` must equal the
	validated payload length. A valid packet is not proof of physical truth.
	"""

	SUPPORTED_SCHEMA_VERSIONS: ClassVar[frozenset[str]] = frozenset({"1.0"})

	schema_version: str
	device_id: str
	session_id: str
	sequence_id: int
	timestamp: str
	sample_count: int
	device_status: DeviceStatus
	signal_quality: float | None = None

	def __post_init__(self) -> None:
		"""Validate envelope fields after validating canonical signal fields."""
		if not isinstance(self.schema_version, str):
			raise TypeError("schema_version must be a string")
		super().__post_init__()
		if self.schema_version not in self.SUPPORTED_SCHEMA_VERSIONS:
			raise ContractVersionError(
				f"unsupported Device Data Contract schema_version: {self.schema_version!r}; "
				f"supported versions: {', '.join(sorted(self.SUPPORTED_SCHEMA_VERSIONS))}"
			)
		for field_name in ("device_id", "session_id"):
			value = getattr(self, field_name)
			if not isinstance(value, str):
				raise TypeError(f"{field_name} must be a string")
			if not value.strip():
				raise ValueError(f"{field_name} must not be empty")
		object.__setattr__(self, "sequence_id", _contract_integer(self.sequence_id, "sequence_id"))
		if self.sequence_id < 0:
			raise ValueError("sequence_id must be non-negative")
		object.__setattr__(self, "sample_count", _contract_integer(self.sample_count, "sample_count"))
		if self.sample_count < 1:
			raise ValueError("sample_count must be at least 1")
		if self.sample_count != len(self.payload):
			raise ValueError("sample_count must equal len(payload)")
		object.__setattr__(self, "timestamp", _utc_timestamp(self.timestamp))
		object.__setattr__(self, "device_status", _coerce_enum(self.device_status, DeviceStatus, "device_status"))
		if self.signal_quality is not None:
			quality = _finite_number(self.signal_quality, "signal_quality")
			if not 0 <= quality <= 1:
				raise ValueError("signal_quality must be between 0 and 1 inclusive")
			object.__setattr__(self, "signal_quality", quality)

	def to_dict(self) -> dict[str, object]:
		"""Return the contract fields as a JSON-compatible mapping."""
		return {
			"schema_version": self.schema_version,
			"device_id": self.device_id,
			"session_id": self.session_id,
			"sequence_id": self.sequence_id,
			"timestamp": self.timestamp,
			"modality": self.modality.value,
			"sample_rate": self.sample_rate,
			"sample_count": self.sample_count,
			"unit": self.unit.value,
			"payload": list(self.payload),
			"signal_quality": self.signal_quality,
			"device_status": self.device_status.value,
		}

	def to_json(self) -> str:
		"""Serialize this packet using the initial JSON representation."""
		return json.dumps(self.to_dict(), allow_nan=False, separators=(",", ":"))

	@classmethod
	def from_dict(cls, value: object) -> DevicePacket:
		"""Validate and construct a packet from a JSON-compatible mapping."""
		if not isinstance(value, Mapping):
			raise TypeError("serialized DevicePacket must be a mapping")
		if "schema_version" in value and value["schema_version"] not in cls.SUPPORTED_SCHEMA_VERSIONS:
			raise ContractVersionError(
				f"unsupported Device Data Contract schema_version: {value['schema_version']!r}; "
				f"supported versions: {', '.join(sorted(cls.SUPPORTED_SCHEMA_VERSIONS))}"
			)
		required = {
			"schema_version", "device_id", "session_id", "sequence_id", "timestamp",
			"modality", "sample_rate", "sample_count", "unit", "payload", "device_status",
		}
		missing = required.difference(value)
		if missing:
			raise ValueError(f"DevicePacket is missing required field(s): {', '.join(sorted(missing))}")
		allowed = required | {"signal_quality"}
		unknown = set(value).difference(allowed)
		if unknown:
			raise ValueError(f"DevicePacket has unsupported field(s): {', '.join(sorted(unknown))}")
		return cls(**value)  # type: ignore[arg-type]

	@classmethod
	def from_json(cls, value: str) -> DevicePacket:
		"""Deserialize JSON and validate it as a DevicePacket."""
		try:
			decoded = json.loads(value)
		except (TypeError, json.JSONDecodeError) as error:
			raise ValueError("DevicePacket JSON is invalid") from error
		return cls.from_dict(decoded)


def _coerce_enum(value: object, enum_type: type[Enum], field_name: str) -> Enum:
	"""Accept a supported enum or its serialized value; reject unknown values."""
	if isinstance(value, enum_type):
		return value
	try:
		return enum_type(value)
	except (TypeError, ValueError):
		supported = ", ".join(member.value for member in enum_type)
		raise ValueError(f"{field_name} must be one of: {supported}") from None


def _finite_number(value: object, field_name: str) -> float:
	"""Convert a real numeric value to float while rejecting bool/non-finite data."""
	if isinstance(value, bool) or not isinstance(value, Real):
		raise TypeError(f"{field_name} must be a numeric value")
	number = float(value)
	if not math.isfinite(number):
		raise ValueError(f"{field_name} must be finite")
	return number


def _contract_integer(value: object, field_name: str) -> int:
	"""Accept JSON integer values, including integral floats, but never bools."""
	if isinstance(value, int) and not isinstance(value, bool):
		return value
	if isinstance(value, float) and math.isfinite(value) and value.is_integer():
		return int(value)
	raise TypeError(f"{field_name} must be an integer")


def _utc_timestamp(value: object) -> str:
	"""Validate an explicit UTC timestamp and normalize it to a trailing Z."""
	if not isinstance(value, str):
		raise TypeError("timestamp must be an RFC 3339 UTC string")
	if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)", value) is None:
		raise ValueError("timestamp must be an RFC 3339 UTC string")
	try:
		parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
	except ValueError:
		raise ValueError("timestamp must be an RFC 3339 UTC string") from None
	if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
		raise ValueError("timestamp must include a UTC timezone")
	# datetime validates calendar fields but only retains microseconds. Preserve
	# the original fraction so normalization never changes the claimed instant.
	return value[:-6] + "Z" if value.endswith("+00:00") else value
