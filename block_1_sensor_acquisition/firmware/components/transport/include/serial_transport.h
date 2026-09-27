#pragma once

#include <vector>

#include "driver/uart.h"
#include "esp_err.h"

namespace mindpulse {

class SerialTransport {
public:
	esp_err_t initialize(uart_port_t uart, int tx_gpio, int rx_gpio, int baud_rate);
	esp_err_t write_packet(const std::vector<uint8_t>& packet);

private:
	uart_port_t uart_ = UART_NUM_MAX;
	void* write_mutex_ = nullptr;
};

}  // namespace mindpulse
