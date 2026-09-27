import uuid

import pytest

from block_1_sensor_acquisition.host.packet_decoder import (
	Modality,
	PacketDecoder,
	SignalChunk,
	encode_packet,
)
from block_1_sensor_acquisition.host.session_recorder import MeasurementSession


def test_packet_decoder_accepts_fragmented_voice_and_ppg_with_independent_rates():
	session_id = uuid.uuid4()
	voice = SignalChunk(
		session_id, Modality.VOICE, 0, 16_000, 2_000_000, (-10, 0, 10, 20)
	)
	ppg = SignalChunk(
		session_id, Modality.PPG, 1, 100, 2_000_000, ((100, 200), (110, 210))
	)
	decoder = PacketDecoder()
	wire = encode_packet(voice) + encode_packet(ppg)

	result = decoder.feed(wire[:13])
	result += decoder.feed(wire[13:])

	assert result == [voice, ppg]
	assert result[0].sample_rate_hz != result[1].sample_rate_hz


def test_session_alignment_uses_common_time_without_resampling():
	session_id = uuid.uuid4()
	session = MeasurementSession(session_id, "esp32-s3-test")
	session.add_chunk(
		SignalChunk(session_id, Modality.VOICE, 0, 4, 0, (1, 2, 3, 4, 5, 6, 7, 8))
	)
	session.add_chunk(
		SignalChunk(
			session_id,
			Modality.PPG,
			1,
			2,
			0,
			((10, 20), (11, 21), (12, 22), (13, 23)),
		)
	)

	window = next(session.aligned_windows(1.0))

	assert window.timestamp_start_us == 0
	assert window.timestamp_end_us == 1_000_000
	assert window.voice_sample_rate_hz == 4
	assert window.ppg_sample_rate_hz == 2
	assert window.voice_samples == (1, 2, 3, 4)
	assert window.ppg_samples == ((10, 20), (11, 21))


def test_session_rejects_overlapping_chunks_for_same_modality():
	session_id = uuid.uuid4()
	session = MeasurementSession(session_id, "esp32-s3-test")
	session.add_chunk(SignalChunk(session_id, Modality.VOICE, 0, 4, 0, (1, 2, 3, 4)))

	with pytest.raises(ValueError, match="must not overlap"):
		session.add_chunk(
			SignalChunk(session_id, Modality.VOICE, 1, 4, 500_000, (5, 6, 7, 8))
		)
