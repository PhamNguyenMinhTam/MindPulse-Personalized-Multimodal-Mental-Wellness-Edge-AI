#include "timestamps.h"

#include <limits>

namespace mindpulse {

uint64_t sample_timestamp_us(uint64_t epoch_us, uint64_t sample_index, uint32_t sample_rate_hz) {
	if (sample_rate_hz == 0) {
		return std::numeric_limits<uint64_t>::max();
	}
	return epoch_us + (sample_index * 1000000ULL) / sample_rate_hz;
}

}  // namespace mindpulse
