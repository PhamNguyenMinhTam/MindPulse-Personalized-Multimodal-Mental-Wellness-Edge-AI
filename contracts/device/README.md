# MindPulse Device Data Contract

`DevicePacket` is the stable, hardware-independent boundary between producer
adapters and MindPulse processing. Adapters may interpret native producer
formats; validation and downstream code use only the canonical packet fields.
The Python implementation is `project.data.models.DevicePacket`; the published
JSON shape is described by `schemas/device_packet.schema.json`.

## Version 1.0 Fields

| Field | Semantics |
| --- | --- |
| `schema_version` | Contract version identifier. Version `1.0` is currently supported. |
| `device_id` | Opaque, non-empty producer/device provenance identifier. DSP must not branch on it. |
| `session_id` | Opaque, non-empty acquisition-session identifier. |
| `sequence_id` | Non-negative integer ordering packets within a stream/session scope. No loss, duplicate, or reordering recovery is implied. |
| `timestamp` | RFC 3339 UTC string for the claimed capture instant of the first payload sample. It represents the producer's claim; no clock accuracy or synchronization is established. |
| `modality` | Controlled `voice` or `physiological` category, independent of sensor model. |
| `sample_rate` | Finite, positive sampling frequency in Hz. |
| `sample_count` | Positive integer equal to the number of values in `payload`. |
| `unit` | Controlled canonical value meaning: `raw_count`, `normalized_amplitude`, or `arbitrary_unit`. |
| `payload` | Non-empty one-dimensional waveform of finite numeric values. Values are not normalized or DSP-processed by contract validation. |
| `signal_quality` | Optional numeric estimate in the inclusive range `[0, 1]`; no quality algorithm or interpretation beyond normalized score is prescribed. |
| `device_status` | Generic operational state: `ready`, `streaming`, `degraded`, `reconnecting`, or `error`. |

All required fields must be present and correctly typed. Validation enforces
controlled vocabularies, finite values, positive rate, non-negative sequence,
UTC timestamp representation, and the cross-field invariant
`sample_count == len(payload)`. Unknown serialized fields are rejected.

Identifiers must contain at least one non-whitespace character. In accordance
with JSON Schema integer semantics, integral numbers such as `0.0` and `2.0`
are accepted for `sequence_id` and `sample_count` and stored as Python integers;
booleans and fractional values are rejected. Timestamp normalization changes
the UTC suffix `+00:00` to `Z` while preserving all fractional-second digits.

> A schema-valid packet is not necessarily a physically correct measurement.
> For example, schema validation cannot prove that a claimed 100 Hz signal was
> physically sampled at 100 Hz.

## Version Policy

The implementation accepts only the explicitly supported version `1.0` and
raises `ContractVersionError` for unsupported versions. Backward-compatible
additions may be introduced under a compatible version policy when existing
consumers can continue to interpret packets unchanged. Renaming/removing fields,
changing field meaning or units, or tightening previously accepted values in a
way that breaks consumers requires a new breaking version. Compatibility is
checked locally; there is no remote schema registry or migration service.

## Serialization

The contract is independent of its serialization or transport. JSON is the
initial representation only. `DevicePacket.to_dict()` produces a
JSON-compatible mapping; `to_json()` and `from_json()` provide a validated JSON
round trip. No binary encoding is defined.

The contract validates representation and internal consistency, not hardware
truth. It does not synchronize clocks, reorder packets, resample signals, or
perform signal-quality estimation, DSP, or inference.
