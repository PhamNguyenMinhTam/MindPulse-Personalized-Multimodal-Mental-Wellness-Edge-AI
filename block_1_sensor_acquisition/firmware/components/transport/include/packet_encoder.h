#pragma once

#include <array>
#include <cstdint>
#include <vector>

namespace mindpulse {

enum class Modality : uint8_t {
	Voice = 1,
	Ppg = 2,
};

using SessionId = std::array<uint8_t, 16>;

std::vector<uint8_t> encode_voice_packet(
	const SessionId& session_id,
	uint32_t sequence,
	uint32_t sample_rate_hz,
	uint64_t timestamp_start_us,
	const int16_t* samples,
	uint32_t sample_count);

std::vector<uint8_t> encode_ppg_packet(
	const SessionId& session_id,
	uint32_t sequence,
	uint32_t sample_rate_hz,
	uint64_t timestamp_start_us,
	const uint32_t* red_ir_pairs,
	uint32_t sample_count);

}  // namespace mindpulse
