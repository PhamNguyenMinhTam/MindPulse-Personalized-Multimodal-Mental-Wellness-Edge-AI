# Block 1: Sensor Acquisition

Block 1 captures voice and PPG as independent sample streams and associates both
with one ESP32-S3 monotonic clock. Different sample rates are expected; the host
aligns intervals by timestamp and does not resample either stream.

## Data path

- INMP441 audio is represented as signed 16-bit mono PCM chunks.
- MAX30102 data is represented as paired unsigned 32-bit red/infrared samples.
- Every chunk carries its modality, session UUID, sequence number, sample rate,
	first-sample timestamp in monotonic microseconds, and sample count.
- The chunk end timestamp is exclusive and derived from the first timestamp,
	sample count, and rate. It is not a second independently measured clock time.
- Host wall-clock time is session metadata only; it is never used to align the
	sensor streams.

The host decoder and recorder are in `host/`. The binary `MP01` framing is
defined in `host/packet_decoder.py`; firmware transport must use the same
little-endian header and CRC-32 format. Keep diagnostic logs off the binary
transport UART.

## Configuration

`configs/acquisition/synchronization.yaml` contains example rates (16 kHz voice,
100 Hz PPG) and window defaults. Change them together with the firmware and
MAX30102 register setup if the hardware uses different rates. They are defaults,
not detected values; each packet remains authoritative for its stream rate.

GPIO assignments are intentionally not hard-coded here. Populate the ESP-IDF
pin configuration from the actual board wiring before enabling hardware reads.

## Host capture

Install `pyserial` in the host environment, connect the ESP32 binary transport,
then consume `read_serial(port)` from `host/serial_reader.py`. Pass each decoded
chunk to `SessionRecorder(device_id).add_chunk(...)` and save with
`SessionRecorder.save_json(...)`. For downstream DSP, call
`MeasurementSession.aligned_windows(...)`; it emits windows only when both
streams meet the configured coverage threshold.
