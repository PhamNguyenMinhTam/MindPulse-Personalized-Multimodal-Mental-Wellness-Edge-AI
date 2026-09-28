import json
import math
import re
from pathlib import Path

import pytest

from project.data.models import ContractVersionError, DevicePacket, DeviceStatus, Modality, SignalUnit


def make_packet(**overrides: object) -> DevicePacket:
	fields: dict[str, object] = {
		"schema_version": "1.0",
		"device_id": "producer-opaque-1",
		"session_id": "session-1",
		"sequence_id": 0,
		"timestamp": "2026-09-28T12:00:00Z",
		"modality": Modality.VOICE,
		"sample_rate": 100,
		"sample_count": 2,
		"unit": SignalUnit.ARBITRARY_UNIT,
		"payload": [1, 2.5],
		"device_status": DeviceStatus.STREAMING,
	}
	fields.update(overrides)
	return DevicePacket(**fields)  # type: ignore[arg-type]


def test_complete_device_packet_is_validated() -> None:
	packet = make_packet(signal_quality=0.5)

	assert packet.schema_version == "1.0"
	assert packet.sample_count == len(packet.payload) == 2
	assert packet.payload == (1.0, 2.5)
	assert packet.signal_quality == 0.5


@pytest.mark.parametrize("sample_rate", [0, -1, math.nan, math.inf, -math.inf])
def test_rejects_invalid_sample_rate(sample_rate: float) -> None:
	with pytest.raises(ValueError, match="sample_rate"):
		make_packet(sample_rate=sample_rate)


def test_rejects_negative_or_non_integer_sequence_id() -> None:
	with pytest.raises(ValueError, match="sequence_id must be non-negative"):
		make_packet(sequence_id=-1)
	with pytest.raises(TypeError, match="sequence_id must be an integer"):
		make_packet(sequence_id=True)


@pytest.mark.parametrize("payload", [[], ["x"], [math.nan], [math.inf]])
def test_rejects_invalid_payload(payload: list[object]) -> None:
	count = len(payload)
	with pytest.raises((TypeError, ValueError), match="payload|sample_count"):
		make_packet(payload=payload, sample_count=count)


def test_rejects_mismatched_sample_count() -> None:
	with pytest.raises(ValueError, match=r"sample_count must equal len\(payload\)"):
		make_packet(sample_count=1)


@pytest.mark.parametrize(
	("field", "value", "message"),
	[
		("modality", "sensor-model-x", "modality must be one of:"),
		("unit", "volts", "unit must be one of:"),
		("device_status", "vendor-state", "device_status must be one of:"),
	],
)
def test_rejects_unsupported_controlled_vocabulary(field: str, value: str, message: str) -> None:
	with pytest.raises(ValueError, match=message):
		make_packet(**{field: value})


@pytest.mark.parametrize("quality", [0, 0.5, 1])
def test_accepts_signal_quality_in_normalized_range(quality: float) -> None:
	assert make_packet(signal_quality=quality).signal_quality == float(quality)


@pytest.mark.parametrize("quality", [-0.01, 1.01, math.nan, math.inf])
def test_rejects_out_of_range_signal_quality(quality: float) -> None:
	with pytest.raises(ValueError, match="signal_quality"):
		make_packet(signal_quality=quality)


def test_accepts_only_supported_schema_version() -> None:
	assert make_packet(schema_version="1.0").schema_version == "1.0"
	with pytest.raises(ContractVersionError, match="unsupported Device Data Contract schema_version"):
		make_packet(schema_version="2.0")


def test_json_round_trip_preserves_packet_semantics() -> None:
	packet = make_packet(signal_quality=0.75)

	assert DevicePacket.from_json(packet.to_json()) == packet
	assert DevicePacket.from_dict(packet.to_dict()) == packet


def test_deserialization_reports_missing_required_fields() -> None:
	with pytest.raises(ValueError, match="missing required field.*sample_count"):
		DevicePacket.from_dict({"schema_version": "1.0"})


@pytest.mark.parametrize("timestamp", ["2026-09-28T12:00:00", "2026-09-28T12:00:00+01:00", "not-a-time"])
def test_timestamp_requires_explicit_utc_instant(timestamp: str) -> None:
	with pytest.raises(ValueError, match="timestamp"):
		make_packet(timestamp=timestamp)


@pytest.mark.parametrize("suffix", ["Z", "+00:00"])
@pytest.mark.parametrize("fraction", ["", ".1", ".123456789", ".123456789012300"])
def test_timestamp_preserves_fraction_through_json_round_trip(suffix: str, fraction: str) -> None:
	base = "2026-09-28T12:00:00" + fraction
	data = make_packet().to_dict()
	data["timestamp"] = base + suffix
	packet = DevicePacket.from_json(json.dumps(data))
	assert packet.timestamp == base + "Z"
	assert DevicePacket.from_json(packet.to_json()).timestamp == base + "Z"


@pytest.mark.parametrize("timestamp", ["2026-02-30T12:00:00.123456789Z", "2026-09-28T25:00:00Z"])
def test_timestamp_still_rejects_invalid_calendar_fields(timestamp: str) -> None:
	with pytest.raises(ValueError, match="timestamp"):
		make_packet(timestamp=timestamp)


@pytest.mark.parametrize("field,value", [("sequence_id", 0.0), ("sequence_id", 12.0), ("sample_count", 2.0)])
def test_json_integral_numbers_are_normalized(field: str, value: float) -> None:
	data = make_packet().to_dict()
	data[field] = value
	packet = DevicePacket.from_json(json.dumps(data))
	assert getattr(packet, field) == int(value)
	assert type(getattr(packet, field)) is int
	assert DevicePacket.from_json(packet.to_json()) == packet


@pytest.mark.parametrize("field", ["sequence_id", "sample_count"])
@pytest.mark.parametrize("value", [True, False, 1.5, "2", None, math.nan, math.inf, -math.inf])
def test_integer_fields_reject_non_integer_values(field: str, value: object) -> None:
	with pytest.raises(TypeError, match=field):
		make_packet(**{field: value})


@pytest.mark.parametrize("field,value", [("sequence_id", -1.0), ("sample_count", 0.0), ("sample_count", 3.0)])
def test_integral_floats_still_obey_count_and_range_constraints(field: str, value: float) -> None:
	with pytest.raises(ValueError, match=field):
		make_packet(**{field: value})


@pytest.mark.parametrize("field", ["device_id", "session_id"])
@pytest.mark.parametrize("value", ["", "   ", "\t\r\n", "\u00a0", "\u2003", " device-1 "])
def test_identifier_schema_constraints_match_runtime(field: str, value: str) -> None:
	schema_path = Path(__file__).resolve().parents[2] / "contracts/device/schemas/device_packet.schema.json"
	constraints = json.loads(schema_path.read_text(encoding="utf-8"))["properties"][field]
	accepted = len(value) >= constraints["minLength"] and re.search(constraints["pattern"], value) is not None
	if accepted:
		assert getattr(make_packet(**{field: value}), field) == value
	else:
		with pytest.raises(ValueError, match=field):
			make_packet(**{field: value})
