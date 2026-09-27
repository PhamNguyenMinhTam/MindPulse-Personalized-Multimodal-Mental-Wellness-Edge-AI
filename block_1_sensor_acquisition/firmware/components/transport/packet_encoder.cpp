#include "packet_encoder.h"

#include <iterator>
#include <utility>

namespace mindpulse {
namespace {

constexpr uint8_t kMagic[] = {'M', 'P', '0', '1'};
constexpr uint8_t kVersion = 1;

void append_u16(std::vector<uint8_t>& out, uint16_t value) {
	out.push_back(static_cast<uint8_t>(value));
	out.push_back(static_cast<uint8_t>(value >> 8));
}

void append_u32(std::vector<uint8_t>& out, uint32_t value) {
	for (unsigned shift = 0; shift < 32; shift += 8) {
		out.push_back(static_cast<uint8_t>(value >> shift));
	}
}

void append_u64(std::vector<uint8_t>& out, uint64_t value) {
	for (unsigned shift = 0; shift < 64; shift += 8) {
		out.push_back(static_cast<uint8_t>(value >> shift));
	}
}

uint32_t crc32(const uint8_t* data, size_t size) {
	uint32_t crc = 0xFFFFFFFFU;
	for (size_t index = 0; index < size; ++index) {
		crc ^= data[index];
		for (int bit = 0; bit < 8; ++bit) {
			const uint32_t mask = 0U - (crc & 1U);
			crc = (crc >> 1) ^ (0xEDB88320U & mask);
		}
	}
	return ~crc;
}

std::vector<uint8_t> packet_prefix(
	Modality modality,
	const SessionId& session_id,
	uint32_t sequence,
	uint32_t sample_rate_hz,
	uint64_t timestamp_start_us,
	uint32_t sample_count,
	uint32_t payload_size) {
	if (sample_rate_hz == 0 || sample_count == 0) {
		return {};
	}
	std::vector<uint8_t> packet;
	packet.reserve(48 + payload_size + 4);
	packet.insert(packet.end(), std::begin(kMagic), std::end(kMagic));
	packet.push_back(kVersion);
	packet.push_back(static_cast<uint8_t>(modality));
	append_u16(packet, 0);
	packet.insert(packet.end(), session_id.begin(), session_id.end());
	append_u32(packet, sequence);
	append_u32(packet, sample_rate_hz);
	append_u64(packet, timestamp_start_us);
	append_u32(packet, sample_count);
	append_u32(packet, payload_size);
	return packet;
}

std::vector<uint8_t> finish_packet(std::vector<uint8_t> packet) {
	if (packet.empty()) {
		return {};
	}
	append_u32(packet, crc32(packet.data(), packet.size()));
	return packet;
}

}  // namespace

std::vector<uint8_t> encode_voice_packet(
	const SessionId& session_id,
	uint32_t sequence,
	uint32_t sample_rate_hz,
	uint64_t timestamp_start_us,
	const int16_t* samples,
	uint32_t sample_count) {
	if (samples == nullptr || sample_count == 0 || sample_count > UINT32_MAX / 8U) {
		return {};
	}
	auto packet = packet_prefix(
		Modality::Voice, session_id, sequence, sample_rate_hz,
		timestamp_start_us, sample_count, sample_count * 2U);
	if (packet.empty()) {
		return {};
	}
	for (uint32_t index = 0; index < sample_count; ++index) {
		append_u16(packet, static_cast<uint16_t>(samples[index]));
	}
	return finish_packet(std::move(packet));
}

std::vector<uint8_t> encode_ppg_packet(
	const SessionId& session_id,
	uint32_t sequence,
	uint32_t sample_rate_hz,
	uint64_t timestamp_start_us,
	const uint32_t* red_ir_pairs,
	uint32_t sample_count) {
	if (red_ir_pairs == nullptr || sample_count == 0 || sample_count > UINT32_MAX / 8U) {
		return {};
	}
	auto packet = packet_prefix(
		Modality::Ppg, session_id, sequence, sample_rate_hz,
		timestamp_start_us, sample_count, sample_count * 8U);
	if (packet.empty()) {
		return {};
	}
	for (uint32_t index = 0; index < sample_count * 2U; ++index) {
		append_u32(packet, red_ir_pairs[index]);
	}
	return finish_packet(std::move(packet));
}

}  // namespace mindpulse
