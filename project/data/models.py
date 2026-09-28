"""Canonical data models shared across MindPulse processing layers."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from numbers import Real
from typing import TypedDict


class Modality(str, Enum):
	"""Supported signal categories, independent of the producing device."""

	VOICE = "voice"
	PHYSIOLOGICAL = "physiological"


class SignalUnit(str, Enum):
	"""Controlled semantic descriptions of canonical payload values."""

	RAW_COUNT = "raw_count"
	NORMALIZED_AMPLITUDE = "normalized_amplitude"
	ARBITRARY_UNIT = "arbitrary_unit"


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
