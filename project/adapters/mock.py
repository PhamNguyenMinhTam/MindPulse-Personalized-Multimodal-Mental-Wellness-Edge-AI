"""Mock adapters for three intentionally incompatible producer formats."""

from __future__ import annotations

from collections.abc import Mapping

from project.adapters.base import require_fields, require_number
from project.data.models import CanonicalSignalCandidate, Modality, SignalUnit


class MockProducerAAdapter:
    """Map ``rate`` and ``values`` into canonical fields; perform no DSP."""

    def __init__(self, modality: Modality, unit: SignalUnit) -> None:
        self._modality = modality
        self._unit = unit

    def adapt(self, packet: Mapping[str, object]) -> CanonicalSignalCandidate:
        """Convert Producer A's native rate/value names to canonical names."""
        require_fields(packet, ("rate", "values"))
        return {
            "modality": self._modality,
            "sample_rate": require_number(packet["rate"], "rate"),
            "unit": self._unit,
            "payload": packet["values"],  # type: ignore[typeddict-item]
        }


class MockProducerBAdapter:
    """Map ``fs`` and ``samples`` into canonical fields; perform no DSP."""

    def __init__(self, modality: Modality, unit: SignalUnit) -> None:
        self._modality = modality
        self._unit = unit

    def adapt(self, packet: Mapping[str, object]) -> CanonicalSignalCandidate:
        """Convert Producer B's native sampling-frequency/sample names."""
        require_fields(packet, ("fs", "samples"))
        return {
            "modality": self._modality,
            "sample_rate": require_number(packet["fs"], "fs"),
            "unit": self._unit,
            "payload": packet["samples"],  # type: ignore[typeddict-item]
        }


class MockProducerCAdapter:
    """Convert ``period_ms`` to Hz and map ``signal`` without DSP."""

    def __init__(self, modality: Modality, unit: SignalUnit) -> None:
        self._modality = modality
        self._unit = unit

    def adapt(self, packet: Mapping[str, object]) -> CanonicalSignalCandidate:
        """Map Producer C fields, converting its millisecond period to Hz."""
        require_fields(packet, ("period_ms", "signal"))
        period_ms = require_number(packet["period_ms"], "period_ms")
        if period_ms <= 0:
            raise ValueError("producer field 'period_ms' must be greater than 0 ms")
        sample_rate = 1.0 / (period_ms / 1000.0)
        return {
            "modality": self._modality,
            "sample_rate": sample_rate,
            "unit": self._unit,
            "payload": packet["signal"],  # type: ignore[typeddict-item]
        }