#pragma once

#include <cstdint>

namespace mindpulse {

uint64_t sample_timestamp_us(uint64_t epoch_us, uint64_t sample_index, uint32_t sample_rate_hz);

}  // namespace mindpulse
