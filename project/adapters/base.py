"""Small interface for producer-specific representation conversion."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from project.data.models import CanonicalSignalCandidate


class SignalAdapter(Protocol):
    """Convert one producer packet to canonical fields without processing it."""

    def adapt(self, packet: Mapping[str, object]) -> CanonicalSignalCandidate:
        """Map producer-specific fields and units to a canonical candidate."""


def require_fields(packet: Mapping[str, object], fields: tuple[str, ...]) -> None:
    """Raise a descriptive error when a producer packet is malformed."""
    if not isinstance(packet, Mapping):
        raise TypeError("producer packet must be a mapping")
    missing = [field for field in fields if field not in packet]
    if missing:
        raise ValueError(f"producer packet is missing required field(s): {', '.join(missing)}")


def require_number(value: object, field_name: str) -> float:
    """Safely convert a native numeric value without accepting strings/bools."""
    from math import isfinite
    from numbers import Real

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"producer field '{field_name}' must be numeric")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"producer field '{field_name}' must be finite")
    return number