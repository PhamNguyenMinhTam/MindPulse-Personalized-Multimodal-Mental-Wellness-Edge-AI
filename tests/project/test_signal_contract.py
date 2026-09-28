import math

import pytest

from project.data.models import CanonicalSignal, Modality, SignalUnit


def make_signal(**overrides: object) -> CanonicalSignal:
    values: dict[str, object] = {
        "modality": Modality.VOICE,
        "sample_rate": 100,
        "unit": SignalUnit.ARBITRARY_UNIT,
        "payload": [1, 2.5],
    }
    values.update(overrides)
    return CanonicalSignal(**values)  # type: ignore[arg-type]


def test_contract_normalizes_valid_payload_to_float_tuple() -> None:
    signal = make_signal()

    assert signal.sample_rate == 100.0
    assert signal.payload == (1.0, 2.5)
    assert isinstance(signal.payload, tuple)


@pytest.mark.parametrize("sample_rate", [0, -1])
def test_contract_rejects_non_positive_sample_rate(sample_rate: float) -> None:
    with pytest.raises(ValueError, match="sample_rate must be greater than 0 Hz"):
        make_signal(sample_rate=sample_rate)


@pytest.mark.parametrize("sample_rate", [math.nan, math.inf, -math.inf])
def test_contract_rejects_non_finite_sample_rate(sample_rate: float) -> None:
    with pytest.raises(ValueError, match="sample_rate must be finite"):
        make_signal(sample_rate=sample_rate)


def test_contract_rejects_non_numeric_sample_rate() -> None:
    with pytest.raises(TypeError, match="sample_rate must be a numeric value"):
        make_signal(sample_rate="100")


def test_contract_rejects_empty_payload() -> None:
    with pytest.raises(ValueError, match="payload must contain at least one sample"):
        make_signal(payload=[])


def test_contract_rejects_non_numeric_payload() -> None:
    with pytest.raises(TypeError, match=r"payload\[1\] must be a numeric value"):
        make_signal(payload=[1, "two"])


@pytest.mark.parametrize("sample", [math.nan, math.inf, -math.inf])
def test_contract_rejects_non_finite_payload(sample: float) -> None:
    with pytest.raises(ValueError, match=r"payload\[1\] must be finite"):
        make_signal(payload=[1, sample])


@pytest.mark.parametrize("modality", ["device_a", "voice-like"])
def test_contract_rejects_unsupported_modality(modality: str) -> None:
    with pytest.raises(ValueError, match="modality must be one of: voice, physiological"):
        make_signal(modality=modality)


def test_contract_rejects_unsupported_unit() -> None:
    with pytest.raises(ValueError, match="unit must be one of:"):
        make_signal(unit="volts")