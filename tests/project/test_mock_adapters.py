import math

import pytest

from project.adapters.mock import MockProducerAAdapter, MockProducerBAdapter, MockProducerCAdapter
from project.data.models import Modality, SignalUnit


MODALITY = Modality.PHYSIOLOGICAL
UNIT = SignalUnit.RAW_COUNT


@pytest.mark.parametrize(
    ("adapter", "packet"),
    [
        (MockProducerAAdapter(MODALITY, UNIT), {"rate": 100, "values": [10, 20, 30]}),
        (MockProducerBAdapter(MODALITY, UNIT), {"fs": 100, "samples": [10, 20, 30]}),
        (MockProducerCAdapter(MODALITY, UNIT), {"period_ms": 10, "signal": [10, 20, 30]}),
    ],
)
def test_incompatible_producers_emit_equivalent_canonical_candidates(adapter: object, packet: dict[str, object]) -> None:
    candidate = adapter.adapt(packet)  # type: ignore[attr-defined]

    assert candidate == {
        "modality": MODALITY,
        "sample_rate": 100.0,
        "unit": UNIT,
        "payload": [10, 20, 30],
    }


@pytest.mark.parametrize("period_ms", [0, -1])
def test_producer_c_rejects_non_positive_period(period_ms: float) -> None:
    adapter = MockProducerCAdapter(MODALITY, UNIT)

    with pytest.raises(ValueError, match="period_ms.*greater than 0 ms"):
        adapter.adapt({"period_ms": period_ms, "signal": [1]})


@pytest.mark.parametrize("period_ms", [math.nan, math.inf])
def test_producer_c_rejects_non_finite_period(period_ms: float) -> None:
    adapter = MockProducerCAdapter(MODALITY, UNIT)

    with pytest.raises(ValueError, match="period_ms.*must be finite"):
        adapter.adapt({"period_ms": period_ms, "signal": [1]})


@pytest.mark.parametrize(
    ("adapter", "packet", "missing_field"),
    [
        (MockProducerAAdapter(MODALITY, UNIT), {"rate": 100}, "values"),
        (MockProducerBAdapter(MODALITY, UNIT), {"samples": [1]}, "fs"),
        (MockProducerCAdapter(MODALITY, UNIT), {"signal": [1]}, "period_ms"),
    ],
)
def test_adapters_explain_missing_native_fields(adapter: object, packet: dict[str, object], missing_field: str) -> None:
    with pytest.raises(ValueError, match=f"missing required field.*{missing_field}"):
        adapter.adapt(packet)  # type: ignore[attr-defined]


def test_adapter_rejects_non_mapping_packet() -> None:
    adapter = MockProducerAAdapter(MODALITY, UNIT)

    with pytest.raises(TypeError, match="producer packet must be a mapping"):
        adapter.adapt(None)  # type: ignore[arg-type]