#pragma once

#include <cstddef>
#include <cstdint>

#include "driver/i2c_master.h"
#include "esp_err.h"

namespace mindpulse {

class Max30102 {
public:
	esp_err_t initialize(int sda_gpio, int scl_gpio, uint32_t sample_rate_hz);
	esp_err_t read_available(
		uint32_t* red_ir_pairs,
		size_t capacity,
		size_t* samples_read,
		uint8_t* samples_lost);
	uint64_t stream_start_timestamp_us() const;

private:
	esp_err_t write_register(uint8_t address, uint8_t value);
	esp_err_t read_registers(uint8_t address, uint8_t* data, size_t size);

	i2c_master_bus_handle_t bus_ = nullptr;
	i2c_master_dev_handle_t device_ = nullptr;
	uint64_t stream_start_timestamp_us_ = 0;
};

}  // namespace mindpulse
