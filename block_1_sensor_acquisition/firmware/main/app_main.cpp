#include <array>

#include "acquisition_tasks.h"
#include "esp_log.h"
#include "esp_random.h"

namespace {

constexpr char kTag[] = "mindpulse_acquisition";

#if CONFIG_MINDPULSE_PPG_RATE_50
constexpr uint32_t kPpgSampleRateHz = 50;
#elif CONFIG_MINDPULSE_PPG_RATE_200
constexpr uint32_t kPpgSampleRateHz = 200;
#elif CONFIG_MINDPULSE_PPG_RATE_400
constexpr uint32_t kPpgSampleRateHz = 400;
#else
constexpr uint32_t kPpgSampleRateHz = 100;
#endif

}  // namespace

extern "C" void app_main() {
	if (CONFIG_MINDPULSE_I2S_BCLK_GPIO < 0 || CONFIG_MINDPULSE_I2S_WS_GPIO < 0 ||
		CONFIG_MINDPULSE_I2S_DATA_GPIO < 0 || CONFIG_MINDPULSE_I2C_SDA_GPIO < 0 ||
		CONFIG_MINDPULSE_I2C_SCL_GPIO < 0 || CONFIG_MINDPULSE_UART_TX_GPIO < 0 ||
		CONFIG_MINDPULSE_UART_RX_GPIO < 0) {
		ESP_LOGE(kTag, "Set all sensor and UART GPIOs in menuconfig before running acquisition");
		return;
	}

	static mindpulse::Inmp441 microphone;
	static mindpulse::Max30102 ppg_sensor;
	static mindpulse::SerialTransport transport;

	esp_err_t result = transport.initialize(
		static_cast<uart_port_t>(CONFIG_MINDPULSE_UART_NUM),
		CONFIG_MINDPULSE_UART_TX_GPIO,
		CONFIG_MINDPULSE_UART_RX_GPIO,
		CONFIG_MINDPULSE_UART_BAUD);
	if (result != ESP_OK) {
		ESP_LOGE(kTag, "UART initialization failed: %s", esp_err_to_name(result));
		return;
	}

	result = ppg_sensor.initialize(
		CONFIG_MINDPULSE_I2C_SDA_GPIO,
		CONFIG_MINDPULSE_I2C_SCL_GPIO,
		kPpgSampleRateHz);
	if (result != ESP_OK) {
		ESP_LOGE(kTag, "MAX30102 initialization failed: %s", esp_err_to_name(result));
		return;
	}

	result = microphone.initialize(
		CONFIG_MINDPULSE_I2S_BCLK_GPIO,
		CONFIG_MINDPULSE_I2S_WS_GPIO,
		CONFIG_MINDPULSE_I2S_DATA_GPIO,
		CONFIG_MINDPULSE_VOICE_RATE_HZ);
	if (result != ESP_OK) {
		ESP_LOGE(kTag, "INMP441 initialization failed: %s", esp_err_to_name(result));
		return;
	}

	mindpulse::SessionId session_id{};
	esp_fill_random(session_id.data(), session_id.size());
	static mindpulse::AcquisitionContext context{
		&microphone,
		&ppg_sensor,
		&transport,
		session_id,
		microphone.stream_start_timestamp_us(),
		ppg_sensor.stream_start_timestamp_us(),
		CONFIG_MINDPULSE_VOICE_RATE_HZ,
		kPpgSampleRateHz,
	};

	result = mindpulse::start_acquisition_tasks(&context);
	if (result != ESP_OK) {
		ESP_LOGE(kTag, "Could not start acquisition tasks: %s", esp_err_to_name(result));
	}
}
