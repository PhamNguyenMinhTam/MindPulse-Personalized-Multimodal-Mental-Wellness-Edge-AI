#include "serial_transport.h"

#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

namespace mindpulse {

esp_err_t SerialTransport::initialize(
	uart_port_t uart, int tx_gpio, int rx_gpio, int baud_rate) {
	if (tx_gpio < 0 || rx_gpio < 0 || baud_rate <= 0 || uart >= UART_NUM_MAX) {
		return ESP_ERR_INVALID_ARG;
	}
	uart_config_t config{};
	config.baud_rate = baud_rate;
	config.data_bits = UART_DATA_8_BITS;
	config.parity = UART_PARITY_DISABLE;
	config.stop_bits = UART_STOP_BITS_1;
	config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
	config.source_clk = UART_SCLK_DEFAULT;

	esp_err_t result = uart_driver_install(uart, 4096, 0, 0, nullptr, 0);
	if (result != ESP_OK) {
		return result;
	}
	result = uart_param_config(uart, &config);
	if (result != ESP_OK) {
		return result;
	}
	result = uart_set_pin(uart, tx_gpio, rx_gpio, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
	if (result != ESP_OK) {
		return result;
	}

	write_mutex_ = xSemaphoreCreateMutex();
	if (write_mutex_ == nullptr) {
		return ESP_ERR_NO_MEM;
	}
	uart_ = uart;
	return ESP_OK;
}

esp_err_t SerialTransport::write_packet(const std::vector<uint8_t>& packet) {
	if (uart_ == UART_NUM_MAX || write_mutex_ == nullptr || packet.empty()) {
		return ESP_ERR_INVALID_STATE;
	}
	if (xSemaphoreTake(static_cast<SemaphoreHandle_t>(write_mutex_), portMAX_DELAY) != pdTRUE) {
		return ESP_ERR_TIMEOUT;
	}
	const int written = uart_write_bytes(
		uart_, reinterpret_cast<const char*>(packet.data()), packet.size());
	xSemaphoreGive(static_cast<SemaphoreHandle_t>(write_mutex_));
	return written == static_cast<int>(packet.size()) ? ESP_OK : ESP_FAIL;
}

}  // namespace mindpulse
