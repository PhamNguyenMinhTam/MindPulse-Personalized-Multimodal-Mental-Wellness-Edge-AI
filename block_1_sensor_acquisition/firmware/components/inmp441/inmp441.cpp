#include "inmp441.h"

#include <algorithm>

#include "esp_timer.h"

namespace mindpulse {

esp_err_t Inmp441::initialize(
	int bclk_gpio, int ws_gpio, int data_gpio, uint32_t sample_rate_hz) {
	if (bclk_gpio < 0 || ws_gpio < 0 || data_gpio < 0 || sample_rate_hz == 0) {
		return ESP_ERR_INVALID_ARG;
	}

	auto channel_config = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
	channel_config.dma_desc_num = 6;
	channel_config.dma_frame_num = 256;
	esp_err_t result = i2s_new_channel(&channel_config, nullptr, &rx_channel_);
	if (result != ESP_OK) {
		return result;
	}

	i2s_std_config_t standard_config{};
	standard_config.clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(sample_rate_hz);
	standard_config.slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(
		I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO);
	standard_config.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;
	standard_config.gpio_cfg.mclk = I2S_GPIO_UNUSED;
	standard_config.gpio_cfg.bclk = static_cast<gpio_num_t>(bclk_gpio);
	standard_config.gpio_cfg.ws = static_cast<gpio_num_t>(ws_gpio);
	standard_config.gpio_cfg.dout = I2S_GPIO_UNUSED;
	standard_config.gpio_cfg.din = static_cast<gpio_num_t>(data_gpio);
	standard_config.gpio_cfg.invert_flags = {};

	result = i2s_channel_init_std_mode(rx_channel_, &standard_config);
	if (result != ESP_OK) {
		return result;
	}
	result = i2s_channel_enable(rx_channel_);
	if (result == ESP_OK) {
		stream_start_timestamp_us_ = static_cast<uint64_t>(esp_timer_get_time());
	}
	return result;
}

esp_err_t Inmp441::read_pcm(
	int16_t* output, size_t capacity, size_t* samples_read, TickType_t timeout) {
	if (rx_channel_ == nullptr || output == nullptr || samples_read == nullptr || capacity == 0) {
		return ESP_ERR_INVALID_ARG;
	}
	const size_t read_capacity = std::min(capacity, raw_buffer_.size());
	size_t bytes_read = 0;
	const esp_err_t result = i2s_channel_read(
		rx_channel_, raw_buffer_.data(), read_capacity * sizeof(int32_t), &bytes_read, timeout);
	if (result != ESP_OK) {
		return result;
	}
	*samples_read = std::min(capacity, bytes_read / sizeof(int32_t));
	for (size_t index = 0; index < *samples_read; ++index) {
		output[index] = static_cast<int16_t>(raw_buffer_[index] >> 16);
	}
	return ESP_OK;
}

uint64_t Inmp441::stream_start_timestamp_us() const {
	return stream_start_timestamp_us_;
}

}  // namespace mindpulse
