"""Orchestrate adaptation and canonical validation before downstream use."""

from __future__ import annotations

from collections.abc import Mapping

from project.adapters.base import SignalAdapter
from project.data.models import CanonicalSignal, DevicePacket, DeviceStatus


class IngestionPipeline:
    """Turn one native packet into a validated device contract packet.

    The pipeline knows only the adapter interface and canonical contract; it
    deliberately does not inspect producer fields or perform DSP/storage.
    """

    def ingest(
        self,
        packet: Mapping[str, object],
        adapter: SignalAdapter,
        *,
        device_id: str,
        session_id: str,
        sequence_id: int,
        timestamp: str,
        device_status: DeviceStatus = DeviceStatus.STREAMING,
        signal_quality: float | None = None,
        schema_version: str = "1.0",
    ) -> DevicePacket:
        """Adapt native fields, then validate the complete contract packet."""
        candidate = adapter.adapt(packet)
        signal = CanonicalSignal(**candidate)
        return DevicePacket(
            **candidate,
            schema_version=schema_version,
            device_id=device_id,
            session_id=session_id,
            sequence_id=sequence_id,
            timestamp=timestamp,
            sample_count=len(signal.payload),
            device_status=device_status,
            signal_quality=signal_quality,
        )