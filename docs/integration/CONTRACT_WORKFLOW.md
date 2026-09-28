# Device Contract Workflow

Producer-specific fields are interpreted only by an adapter. The adapter emits
the existing canonical signal candidate (`modality`, `sample_rate`, `unit`, and
`payload`); ingestion validates those waveform fields, attaches explicit packet
provenance/session/sequence/time metadata, and validates a `DevicePacket` before
returning it to downstream consumers.

```text
native producer packet -> adapter -> canonical signal candidate
	-> DevicePacket validation -> downstream DSP / storage / monitoring
```

Invalid candidates or packet metadata raise an explicit validation error and
are not returned by ingestion. Downstream code must use contract fields only;
producer names such as `rate`, `fs`, `period_ms`, `values`, `samples`, and
`signal` remain adapter-internal.

See [the Device Data Contract](../../contracts/device/README.md) for field
semantics, validation, versioning, and JSON representation. Schema-valid does
not mean physically accurate: the producer's sampling-rate and timestamp claims
cannot be established from packet structure alone.
