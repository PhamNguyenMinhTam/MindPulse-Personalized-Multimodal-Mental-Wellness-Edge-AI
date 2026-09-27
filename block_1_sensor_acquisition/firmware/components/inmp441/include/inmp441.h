#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

#include "freertos/FreeRTOS.h"
#include "driver/i2s_std.h"
#include "esp_err.h"

namespace mindpulse {

class Inmp441 {
public:
	esp_err_t initialize(int bclk_gpio, int ws_gpio, int data_gpio, uint32_t sample_rate_hz);
	esp_err_t read_pcm(int16_t* output, size_t capacity, size_t* samples_read, TickType_t timeout);
	uint64_t stream_start_timestamp_us() const;

private:
	i2s_chan_handle_t rx_channel_ = nullptr;
	uint64_t stream_start_timestamp_us_ = 0;
	std::array<int32_t, 256> raw_buffer_{};
};

}  // namespace mindpulse
