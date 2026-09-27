#pragma once

#include "esp_err.h"
#include "inmp441.h"
#include "max30102.h"
#include "packet_encoder.h"
#include "serial_transport.h"

namespace mindpulse {

struct AcquisitionContext {
	Inmp441* microphone;
	Max30102* ppg_sensor;
	SerialTransport* transport;
	SessionId session_id;
	uint64_t voice_start_us;
	uint64_t ppg_start_us;
	uint32_t voice_rate_hz;
	uint32_t ppg_rate_hz;
};

esp_err_t start_acquisition_tasks(AcquisitionContext* context);

}  // namespace mindpulse
