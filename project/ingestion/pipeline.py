"""Orchestrate adaptation and canonical validation before downstream use."""

from __future__ import annotations

from collections.abc import Mapping

from project.adapters.base import SignalAdapter
from project.data.models import CanonicalSignal


class IngestionPipeline:
    """Turn one native packet into a validated canonical signal.

    The pipeline knows only the adapter interface and canonical contract; it
    deliberately does not inspect producer fields or perform DSP/storage.
    """

    def ingest(self, packet: Mapping[str, object], adapter: SignalAdapter) -> CanonicalSignal:
        """Adapt, validate by constructing the contract model, and return it."""
        candidate = adapter.adapt(packet)
        return CanonicalSignal(**candidate)