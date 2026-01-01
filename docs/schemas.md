# Data Schemas (P1)

This document defines the canonical message and query shapes used by the Digital Twin for Plant Health Monitoring. Schemas are expressed as Python `dataclasses` and serialized to JSON for transport and storage. Each schema includes field semantics, constraints, and example payloads.

> **Timestamps:** Unless otherwise noted, timestamps are **Unix epoch seconds (float)**. When interacting with JavaScript/Plotly/SocketIO, convert to **milliseconds**.

> **Correlation IDs:** Every event/command carries a `correlation_id` (UUID-like string) to stitch together sensor readings, alerts, and actions produced by the same causal chain.

---

## Versioning & Evolution

* The Python classes are the **source of truth**. Backward-compatible evolution should prefer **additive** changes (adding optional fields) over breaking ones (renaming or removing fields).
* When a breaking change is unavoidable, bump the package version and record the change in **Schema Changelog** (appendix) and ensure consumers are migrated.
* Consider adding an optional `schema_version: str` in future revisions if cross-language consumers appear.

---

## Common Conventions

* **IDs** are integers for entities that live in the DT domain (e.g., `plant_id`, `sensor_id`, `actuator_id`).
* **Enumerations** are strings constrained to a closed set (e.g., `command`, `severity`) or first-class Enums in Python.
* **Units** use SI where possible (e.g., `°C`, `%`, `lux`).

---

## Base: `JsonSerializable`

**Purpose:** Provide consistent JSON (de)serialization and minimal validation.

**Behavior:**

* `to_dict()` / `to_json()` produce a canonical JSON representation.
* `from_dict()` / `from_json()` enforce required fields and basic type-casting.
* `validate_json()` returns a boolean by attempting parsing.

No wire shape of its own; it’s inherited by all schemas below.

---

## Message: `SensorData`

**Purpose:** Transport a single reading from a physical/virtual sensor.

**Fields**

| Field            |            Type | Required | Constraints / Notes                                                  |
| ---------------- | --------------: | :------: | -------------------------------------------------------------------- |
| `plant_id`       |             int |     ✓    | Owning plant instance.                                               |
| `sensor_id`      |             int |     ✓    | Unique within `plant_id`.                                            |
| `timestamp`      |           float |     ✓    | Unix seconds. Use `py_to_js_timestamp()` for ms when emitting to JS. |
| `value`          |           float |     ✓    | Calibrated numeric value.                                            |
| `unit`           |             str |     ✓    | Measurement unit (e.g., `%`, `°C`, `lux`).                           |
| `topic`          | `Topics` (Enum) |     ✓    | Routing topic; `data_type` property exposes the short sensor type.   |
| `correlation_id` |             str |     ✓    | Traceability across alerts/actions.                                  |

**Derived**

* `data_type` (property): extracted from `topic.short_name` (e.g., `"soil_moisture"`).

**Example (JSON)**

```json
{
  "plant_id": 1,
  "sensor_id": 12,
  "timestamp": 1728307200.532,
  "value": 34.7,
  "unit": "%",
  "topic": "dt.sensors.soil_moisture",
  "correlation_id": "6b1b9af8-1a57-4742-8c9c-3a5f38f5b6b1"
}
```

**Validation**

* Required fields enforced by `from_dict`. `__post_init__` coerces types.
* Range checks (e.g., 0–100 for `%`) are performed in the preprocessing pipeline, not in the dataclass.

---

## Catalog: `Topics` (Enum)

**Purpose:** Normalize message routing and encode sensor/event data types. Backed by a `StrEnum` that serializes as plain strings on the wire.

**Canonical values**

| Enum member       | Wire value                   | `short_name`      | Notes                                                                      |
| ----------------- | ---------------------------- | ----------------- | -------------------------------------------------------------------------- |
| `SENSORS_DATA`    | `dt.sensors.data`            | `data`            | Aggregate/legacy fan-in for sensor payloads (not used by `list_topics()`). |
| `TEMPERATURE`     | `dt.sensors.temperature`     | `temperature`     | Ambient temperature sensor data.                                           |
| `HUMIDITY`        | `dt.sensors.humidity`        | `humidity`        | Ambient relative humidity sensor data.                                     |
| `SOIL_MOISTURE`   | `dt.sensors.soil_moisture`   | `soil_moisture`   | Soil moisture readings (normalized or raw, see preprocessing spec).        |
| `LIGHT_INTENSITY` | `dt.sensors.light_intensity` | `light_intensity` | Lux or normalized light level.                                             |
| `CAMERA_IMAGE`    | `dt.sensors.camera_image`    | `camera_image`    | Frames or snapshots produced by the camera pipeline.                       |
| `ALERTS`          | `dt.alerts`                  | `alerts`          | System alerts/notifications.                                               |
| `ACTIONS`         | `dt.actions`                 | `actions`         | Actuator commands (mirrors `ActionCommand`).                               |

**Helpers & behavior**

* `Topics.list_topics()` returns all enum values **except** `SENSORS_DATA` (and the raw prefix constant), so iteration yields concrete topics for production use.
* `Topics.short_name` returns the trailing segment (e.g., `dt.sensors.soil_moisture → soil_moisture`).
* `Topics.raw` derives a raw-ingest topic as `dt.sensors.raw.<short_name>` (e.g., `dt.sensors.raw.temperature`).
* `Topics.processed` derives a validated stream as `dt.sensors.processed.<short_name>`.
* `Topics.from_short_name(name)` maps a short name to its enum member (case-insensitive via `.upper()`).

**Examples**

```text
Topics.SOIL_MOISTURE.value      == "dt.sensors.soil_moisture"
Topics.SOIL_MOISTURE.short_name == "soil_moisture"
Topics.SOIL_MOISTURE.raw        == "dt.sensors.raw.soil_moisture"
Topics.SOIL_MOISTURE.processed  == "dt.sensors.processed.soil_moisture"
```

---

## Entity: `SensorDescriptor`

**Purpose:** Static configuration/metadata for a sensor installed on the plant.

**Fields**

| Field           | Type | Required | Constraints / Notes                |
| --------------- | ---: | :------: | ---------------------------------- |
| `sensor_id`     |  int |     ✓    | Matches `SensorData.sensor_id`.    |
| `name`          |  str |     ✓    | Human-readable label.              |
| `pin`           |  int |     ✓    | Physical GPIO pin (BCM numbering). |
| `read_interval` |  int |     ✓    | Seconds between reads.             |

**Example (JSON)**

```json
{
  "sensor_id": 12,
  "name": "Soil Moisture #1",
  "pin": 17,
  "read_interval": 5
}
```

**Notes**

* Use this schema to build configuration UIs and enforce safe polling intervals.

---

## Query: `DBTimestampQuery`

**Purpose:** Retrieve data for a given data type within a time window.

**Fields**

| Field       |  Type | Required | Constraints / Notes                                                       |
| ----------- | ----: | :------: | ------------------------------------------------------------------------- |
| `data_type` |   str |     ✓    | Should match `SensorData.data_type` (e.g., `"soil_moisture"`).            |
| `since`     | float |     ✓    | Start time (Unix seconds). Use `js_to_py_timestamp()` to convert from ms. |
| `until`     | float |     ✓    | End time (Unix seconds). Must be ≥ `since`.                               |

**Example (JSON)**

```json
{
  "data_type": "soil_moisture",
  "since": 1728300000.0,
  "until": 1728307200.0
}
```

**Notes**

* The API should validate that `until - since` does not exceed configured limits to protect the DB.

---

## Query: `DBIdQuery`

**Purpose:** Retrieve latest readings for a specific sensor.

**Fields**

| Field       | Type | Required | Constraints / Notes                            |
| ----------- | ---: | :------: | ---------------------------------------------- |
| `sensor_id` |  int |     ✓    | Must be ≥ 1.                                   |
| `limit`     |  int |     ✓    | Must be ≥ 1; max capped by API (e.g., 10,000). |

**Example (JSON)**

```json
{
  "sensor_id": 12,
  "limit": 500
}
```

**Validation**

* `__post_init__` raises if `limit < 1` or `sensor_id < 1`.

---

## Command: `ActionCommand`

**Purpose:** Instruction to an actuator generated by rules or operator input.

**Fields**

| Field            |  Type | Required | Constraints / Notes                                             |
| ---------------- | ----: | :------: | --------------------------------------------------------------- |
| `plant_id`       |   int |     ✓    | Owning plant instance.                                          |
| `action_id`      |   str |     ✓    | Unique identifier of this action (UUID recommended).            |
| `actuator_id`    |   int |     ✓    | Target actuator.                                                |
| `timestamp`      | float |     ✓    | Command emission time (Unix seconds).                           |
| `duration`       | float |     ✓    | Seconds; `0` for instantaneous actions.                         |
| `command`        |   str |     ✓    | e.g., `"ON"`, `"OFF"`, `"SET_PWM:0.6"`. Consider an Enum later. |
| `reason`         |   str |     ✓    | Human-readable cause, e.g., `"moisture below threshold"`.       |
| `correlation_id` |   str |     ✓    | Ties back to triggering data/alert.                             |

**Example (JSON)**

```json
{
  "plant_id": 1,
  "action_id": "act-2c7fb1f8",
  "actuator_id": 5,
  "timestamp": 1728307210.1,
  "duration": 30.0,
  "command": "ON",
  "reason": "moisture below threshold",
  "correlation_id": "6b1b9af8-1a57-4742-8c9c-3a5f38f5b6b1"
}
```

**Notes**

* Persist every command to the Action/Audit store with execution result (success/failure) for traceability.

---

## Events: `SensorAlertEvent` / `ExternalAlertEvent`

**Purpose:** Persist and emit alert lifecycle entries keyed by `alert_key` and `plant_id`.

**Shared fields (AlertHistoryEvent)**

| Field              |  Type | Required | Constraints / Notes                                         |
| ------------------ | ----: | :------: | ----------------------------------------------------------- |
| `alert_key`        |   str |     ✓    | Stable key (rule-based: `{rule_id}:{source}`; external: any) |
| `plant_id`         |   int |     ✓    | Owning plant instance.                                      |
| `timestamp`        | float |     ✓    | Event time (Unix seconds).                                  |
| `status`           |   str |     ✓    | `active`/`suppressed`/`acknowledged`/`cleared`.             |
| `severity`         |   str |     ✓    | Enum: `info`/`warning`/`error`/`critical`.                  |
| `message`          |   str |     ✓    | Human-readable message.                                     |
| `correlation_id`   |   str |     ✓    | Trace identifier.                                           |
| `acknowledged_by`  |   str |     -    | Actor when status is `acknowledged`.                        |
| `acknowledged_ts`  | float |     -    | Timestamp when acknowledged.                                |
| `cleared_ts`       | float |     -    | Timestamp when cleared.                                     |

**SensorAlertEvent additions**

| Field             |  Type | Required | Constraints / Notes                            |
| ----------------- | ----: | :------: | ---------------------------------------------- |
| `reading`         |   obj |     ✓    | `ProcessedSensorData` snapshot.                |
| `threshold_op`    |   str |     -    | For threshold rules (`>`, `<`, `>=`, etc.).    |
| `threshold_value` | float |     -    | Threshold value when applicable.               |
| `range_min`       | float |     -    | Lower bound for range rules.                   |
| `range_max`       | float |     -    | Upper bound for range rules.                   |

**ExternalAlertEvent additions**

| Field      |  Type | Required | Constraints / Notes        |
| ---------- | ----: | :------: | -------------------------- |
| `metadata` |  dict |     ✓    | JSON-serializable context. |

**Notes**

* Alert definitions (persistence, cooldown, source, rule metadata) live in `alert_definitions` keyed by `(alert_key, plant_id)` and must exist before history rows are written.
* Registry ensures persistence/cooldown before emitting; storage guards upsert definitions on insert for safety.

---

## Transport & Storage

* **Wire format:** JSON (compact separators, UTF‑8). Enum values are serialized to their string representation.
* **Kafka topics (suggested):**

  * `dt.sensor.raw` → raw readings (optional if preprocessing on-edge).
  * `dt.sensor.proc` → validated/processed `SensorData`.
  * `dt.alerts` → `AlertHistoryEvent` (`SensorAlertEvent` / `ExternalAlertEvent`).
  * `dt.actions` → `ActionCommand`.
* **InfluxDB measurements (suggested):**

  * `sensor_data` tags: `plant_id`, `sensor_id`, `data_type`, fields: `value`, `unit`.
  * `alerts` fields: `severity`, `description` (also keep in relational store for joins).
  * `actions` fields: `command`, `duration`, `result`.

---

## Error Handling & Validation Strategy

* Parsing errors: `validate_json()` before ingest
* TODO: Business validation (ranges, rate-of-change, stuck sensor): handled by the preprocessing pipeline; annotate rejected points with an error code.
* All validators must preserve `correlation_id` for auditability.

---

## Appendix A — Field Dictionary

* **`plant_id` (int):** Numeric identifier for a plant digital twin instance.
* **`sensor_id` (int):** Numeric identifier of a sensor within a plant context.
* **`actuator_id` (int):** Numeric identifier of an actuator within a plant context.
* **`timestamp` (float):** Unix epoch seconds; precision to milliseconds acceptable.
* **`value` (float):** Calibrated measurement value in the indicated `unit`.
* **`unit` (str):** Unit label (e.g., `%`, `°C`, `lux`).
* **`topic` (`Topics`):** Routing enum; serialized as string; provides `.short_name`.
* **`data_type` (str, derived):** Normalized sensor type derived from `topic`.
* **`correlation_id` (str):** A unique string used to correlate messages across the system.

---

## Appendix B — Schema Changelog

*Initialize on first release.*

* **2025‑10‑07:** P1 baseline. Defined `SensorData`, `SensorDescriptor`, `DBTimestampQuery`, `DBIdQuery`, `ActionCommand`, `AlertEvent`. Added guidance on Topics enum, transport, and validation.
* **2025‑11‑10:** Replaced `AlertEvent`/`CandidateAlert` with `AlertDefinition` + `AlertHistoryEvent` (`SensorAlertEvent`/`ExternalAlertEvent`) keyed by `alert_key`/`plant_id` with persistence/cooldown metadata.
