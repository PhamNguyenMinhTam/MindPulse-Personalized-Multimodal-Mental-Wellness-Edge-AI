#include "acquisition_tasks.h"

#include <array>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "timestamps.h"

namespace mindpulse {
namespace {

constexpr size_t kVoiceChunkSamples = 256;
constexpr size_t kPpgChunkSamples = 32;

void voice_task(void* argument) {
	auto* context = static_cast<AcquisitionContext*>(argument);
	std::array<int16_t, kVoiceChunkSamples> samples{};
	uint64_t sample_index = 0;
	uint32_t sequence = 0;
	while (true) {
		size_t samples_read = 0;
		const esp_err_t result = context->microphone->read_pcm(
			samples.data(), samples.size(), &samples_read, pdMS_TO_TICKS(1000));
		if (result != ESP_OK || samples_read == 0) {
			vTaskDelay(pdMS_TO_TICKS(10));
			continue;
		}
		const auto timestamp = sample_timestamp_us(context->voice_start_us, sample_index, context->voice_rate_hz);
		const auto packet = encode_voice_packet(
			context->session_id, sequence++, context->voice_rate_hz, timestamp,
			samples.data(), static_cast<uint32_t>(samples_read));
		context->transport->write_packet(packet);
		sample_index += samples_read;
	}
}

void ppg_task(void* argument) {
	auto* context = static_cast<AcquisitionContext*>(argument);
	std::array<uint32_t, kPpgChunkSamples * 2> red_ir_pairs{};
	uint64_t sample_index = 0;
	uint32_t sequence = 0;
	while (true) {
		size_t samples_read = 0;
		uint8_t samples_lost = 0;
		const esp_err_t result = context->ppg_sensor->read_available(
			red_ir_pairs.data(), kPpgChunkSamples, &samples_read, &samples_lost);
		if (result == ESP_OK && samples_read > 0) {
			const auto timestamp = sample_timestamp_us(context->ppg_start_us, sample_index, context->ppg_rate_hz);
			const auto packet = encode_ppg_packet(
				context->session_id, sequence++, context->ppg_rate_hz, timestamp,
				red_ir_pairs.data(), static_cast<uint32_t>(samples_read));
			context->transport->write_packet(packet);
			sample_index += samples_read + samples_lost;
		} else if (result == ESP_OK && samples_lost > 0) {
			sample_index += samples_lost;
		}
		vTaskDelay(pdMS_TO_TICKS(5));
	}
}

}  // namespace

esp_err_t start_acquisition_tasks(AcquisitionContext* context) {
	if (context == nullptr || context->microphone == nullptr || context->ppg_sensor == nullptr ||
		context->transport == nullptr || context->voice_rate_hz == 0 || context->ppg_rate_hz == 0) {
		return ESP_ERR_INVALID_ARG;
	}
	if (xTaskCreate(voice_task, "voice_acquisition", 4096, context, 5, nullptr) != pdPASS) {
		return ESP_ERR_NO_MEM;
	}
	if (xTaskCreate(ppg_task, "ppg_acquisition", 4096, context, 5, nullptr) != pdPASS) {
		return ESP_ERR_NO_MEM;
	}
	return ESP_OK;
}

}  // namespace mindpulse
