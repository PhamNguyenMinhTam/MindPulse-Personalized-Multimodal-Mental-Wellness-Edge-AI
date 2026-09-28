import pytest

from project.adapters.mock import MockProducerAAdapter, MockProducerBAdapter, MockProducerCAdapter
from project.data.models import DevicePacket, Modality, SignalUnit
from project.ingestion.pipeline import IngestionPipeline


def test_pipeline_accepts_each_native_format_and_returns_canonical_signal() -> None:
    pipeline = IngestionPipeline()
    cases = [
        (MockProducerAAdapter(Modality.VOICE, SignalUnit.ARBITRARY_UNIT), {"rate": 100, "values": [10, 20]}),
        (MockProducerBAdapter(Modality.VOICE, SignalUnit.ARBITRARY_UNIT), {"fs": 100, "samples": [10, 20]}),
        (MockProducerCAdapter(Modality.VOICE, SignalUnit.ARBITRARY_UNIT), {"period_ms": 10, "signal": [10, 20]}),
    ]

    metadata = {
        "device_id": "mock-device",
        "session_id": "session-1",
        "sequence_id": 0,
        "timestamp": "2026-09-28T12:00:00Z",
    }
    outputs = [pipeline.ingest(packet, adapter, **metadata) for adapter, packet in cases]

    assert all(isinstance(output, DevicePacket) for output in outputs)
    assert outputs[0] == outputs[1] == outputs[2]


@pytest.mark.parametrize(
    ("adapter", "packet", "message"),
    [
        (MockProducerAAdapter(Modality.VOICE, SignalUnit.ARBITRARY_UNIT), {"rate": 0, "values": [1]}, "sample_rate must be greater than 0 Hz"),
        (MockProducerBAdapter(Modality.VOICE, SignalUnit.ARBITRARY_UNIT), {"fs": 100, "samples": []}, "payload must contain at least one sample"),
        (MockProducerCAdapter(Modality.VOICE, SignalUnit.ARBITRARY_UNIT), {"period_ms": 5, "signal": [float("nan")]}, r"payload\[0\] must be finite"),
    ],
)
def test_invalid_data_fails_during_ingestion_before_downstream(adapter: object, packet: dict[str, object], message: str) -> None:
    pipeline = IngestionPipeline()

    with pytest.raises((TypeError, ValueError), match=message):
        pipeline.ingest(
            packet,
            adapter,  # type: ignore[arg-type]
            device_id="mock-device",
            session_id="session-1",
            sequence_id=0,
            timestamp="2026-09-28T12:00:00Z",
        )