#include "max30102.h"

#include <algorithm>
#include <array>

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace mindpulse {
namespace {

constexpr uint8_t kAddress = 0x57;
constexpr uint8_t kFifoWritePointer = 0x04;
constexpr uint8_t kFifoOverflowCounter = 0x05;
constexpr uint8_t kFifoReadPointer = 0x06;
constexpr uint8_t kFifoData = 0x07;

uint8_t sample_rate_code(uint32_t sample_rate_hz) {
	switch (sample_rate_hz) {
		case 50: return 0;
		case 100: return 1;
		case 200: return 2;
		case 400: return 3;
		default: return 0xFF;
	}
}

uint32_t decode_sample(const uint8_t* bytes) {
	return (static_cast<uint32_t>(bytes[0] & 0x03U) << 16) |
		   (static_cast<uint32_t>(bytes[1]) << 8) |
		   static_cast<uint32_t>(bytes[2]);
}

}  // namespace

esp_err_t Max30102::initialize(int sda_gpio, int scl_gpio, uint32_t sample_rate_hz) {
	const uint8_t rate_code = sample_rate_code(sample_rate_hz);
	if (sda_gpio < 0 || scl_gpio < 0 || rate_code == 0xFF) {
		return ESP_ERR_INVALID_ARG;
	}

	i2c_master_bus_config_t bus_config{};
	bus_config.i2c_port = I2C_NUM_0;
	bus_config.sda_io_num = static_cast<gpio_num_t>(sda_gpio);
	bus_config.scl_io_num = static_cast<gpio_num_t>(scl_gpio);
	bus_config.clk_source = I2C_CLK_SRC_DEFAULT;
	bus_config.glitch_ignore_cnt = 7;
	bus_config.intr_priority = 0;
	bus_config.trans_queue_depth = 0;
	bus_config.flags.enable_internal_pullup = true;
	esp_err_t result = i2c_new_master_bus(&bus_config, &bus_);
	if (result != ESP_OK) return result;

	i2c_device_config_t device_config{};
	device_config.dev_addr_length = I2C_ADDR_BIT_LEN_7;
	device_config.device_address = kAddress;
	device_config.scl_speed_hz = 400000;
	result = i2c_master_bus_add_device(bus_, &device_config, &device_);
	if (result != ESP_OK) return result;

	result = write_register(0x09, 0x40);
	if (result != ESP_OK) return result;
	vTaskDelay(pdMS_TO_TICKS(10));
	result = write_register(0x08, 0x0F);
	if (result != ESP_OK) return result;
	result = write_register(0x04, 0x00);
	if (result != ESP_OK) return result;
	result = write_register(0x05, 0x00);
	if (result != ESP_OK) return result;
	result = write_register(0x06, 0x00);
	if (result != ESP_OK) return result;
	result = write_register(0x0A, static_cast<uint8_t>(0x23U | (rate_code << 2)));
	if (result != ESP_OK) return result;
	result = write_register(0x0C, 0x24);
	if (result != ESP_OK) return result;
	result = write_register(0x0D, 0x24);
	if (result != ESP_OK) return result;
	result = write_register(0x09, 0x03);
	if (result == ESP_OK) {
		stream_start_timestamp_us_ = static_cast<uint64_t>(esp_timer_get_time()) +
									 (1000000ULL / sample_rate_hz);
	}
	return result;
}

esp_err_t Max30102::read_available(
	uint32_t* red_ir_pairs,
	size_t capacity,
	size_t* samples_read,
	uint8_t* samples_lost) {
	if (device_ == nullptr || red_ir_pairs == nullptr || samples_read == nullptr ||
		samples_lost == nullptr || capacity == 0) {
		return ESP_ERR_INVALID_ARG;
	}
	*samples_read = 0;
	*samples_lost = 0;
	std::array<uint8_t, 1> write_pointer{};
	std::array<uint8_t, 1> overflow_counter{};
	std::array<uint8_t, 1> read_pointer{};
	esp_err_t result = read_registers(kFifoWritePointer, write_pointer.data(), write_pointer.size());
	if (result != ESP_OK) return result;
	result = read_registers(kFifoOverflowCounter, overflow_counter.data(), overflow_counter.size());
	if (result != ESP_OK) return result;
	result = read_registers(kFifoReadPointer, read_pointer.data(), read_pointer.size());
	if (result != ESP_OK) return result;

	size_t available = (write_pointer[0] - read_pointer[0]) & 0x1FU;
	if (available == 0 && overflow_counter[0] > 0) {
		available = 32;
	}
	const size_t count = std::min(available, capacity);
	std::array<uint8_t, 6> sample{};
	for (size_t index = 0; index < count; ++index) {
		result = read_registers(kFifoData, sample.data(), sample.size());
		if (result != ESP_OK) return result;
		red_ir_pairs[index * 2] = decode_sample(sample.data());
		red_ir_pairs[index * 2 + 1] = decode_sample(sample.data() + 3);
	}
	if (overflow_counter[0] > 0) {
		result = write_register(kFifoOverflowCounter, 0x00);
		if (result != ESP_OK) return result;
		*samples_lost = overflow_counter[0];
	}
	*samples_read = count;
	return ESP_OK;
}

esp_err_t Max30102::write_register(uint8_t address, uint8_t value) {
	const std::array<uint8_t, 2> data{address, value};
	return i2c_master_transmit(device_, data.data(), data.size(), 100);
}

esp_err_t Max30102::read_registers(uint8_t address, uint8_t* data, size_t size) {
	return i2c_master_transmit_receive(device_, &address, 1, data, size, 100);
}

uint64_t Max30102::stream_start_timestamp_us() const {
	return stream_start_timestamp_us_;
}

}  // namespace mindpulse
