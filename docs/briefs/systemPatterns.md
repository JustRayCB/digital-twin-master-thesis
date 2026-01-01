> Topics: dt.raw.sensor, dt.proc.sensor, dt.alerts
> IDs: correlation_id propagated end-to-end
> Storage: PostgreSQL + TimescaleDB (unified time-series hypertables + relational tables)  

# Design Patterns, Coding Standards

## Architecture & Design Patterns

The project embraces a **Microservices and Event-Driven** design pattern. Each
functional area (sensing, preprocessing, storage, analytics, UI) is implemented
as an independent service/module, communicating via a **publish-subscribe**
model (Kafka topics) and REST interfaces. This is essentially an **event-driven
architecture**: sensors produce events, and multiple consumers (data cleaner,
database, ML, UI) react to those events. The benefits of this pattern are
evident in the system's flexibility and scalability as new sensor types or new
processing modules can be added by simply introducing a new Kafka topic and
consumer, without disrupting existing components. Moreover, the use of Kafka
decouples producers and consumers in time, if one component goes down
temporarily, Kafka buffers the data, and consumers can catch up, which adds
resilience.

The **Observer pattern** is inherent in how components subscribe to Kafka
topics (the broker notifies subscribers of new messages). For example, the web
dashboard and AI service both observe the stream of processed sensor data and
react accordingly. Similarly, the alerting mechanism (part of the AI/analytics
module) observes the incoming data for threshold breaches.

Another key pattern is the separation of **concerns and layering** in the
system. The data flow pipeline is segmented: acquisition -> preprocessing ->
storage/analysis -> presentation. By clearly separating these stages, the
system follows a **pipeline pattern** where each stage transforms or handles
data and passes it along. This makes the workflow easier to manage and test in
pieces.

Within preprocessing, a dedicated **StateProvider abstraction** shields the validation,
imputation, and smoothing layers from Spark internals. `SparkStateProvider` translates
`GroupState` payloads into the typed `SensorState` dataclass so that historical context,
flatline markers, and rolling windows stay consistent in both streaming code and unit
tests. This keeps the pipeline deterministic and swappable should state storage move
outside Spark.

The codebase heavily utilizes **Object-Oriented Programming (OOP)** principles
within each module. Classes and objects represent key abstractions (e.g., a
SensorManager class for the data collector, or a KafkaService in the communication module).
This OOP approach promotes encapsulation and reusability, it is
explicitly noted that each module's implementation encourages code reuse and
ease of extension as the system evolves. This pattern means that if a new
sensor needs to be integrated or a new algorithm added, the developers can
subclass or extend existing classes rather than rewriting functionality,
maintaining a clean structure.

For future development, the architecture is set to incorporate patterns
relevant to control systems and MLOps. The Phase P2 **closed-loop control**
introduces a classic **feedback control pattern**: sensor data -> decision
logic -> actuation -> effect on environment -> new sensor data. The software
will include controllers (likely implemented with simple rule-based or PID
patterns) that adjust actuators based on sensor feedback. This will be done in
a safe manner (with interlocks and manual override), following design patterns
from control engineering (e.g., fail-safes, hysteresis in control to avoid
rapid toggling).

On the analytics side (Phase P3), the project plans to adopt an **MLOps**
pattern by integrating a **model registry** and pipeline for training/serving
models. The use of MLflow or a similar tool for model versioning is
anticipated. This introduces patterns like **Continuous Training/Deployment**
of models and monitoring for model drift (triggering retraining or alerts when
performance drops). While these are beyond the current implementation, they
shape the system's architecture: for instance, the AI module is being built
with a placeholder model registry hook in mind so that in future, models can be
swapped or updated seamlessly.

It's also worth highlighting the **audit trail** pattern used for system
actions. Every important event (control commands issued, alerts generated,
configuration changes) will produce a log entry with a unique correlation ID
that ties together cause and effect through the system. This pattern of
**correlation IDs propagated end-to-end** is a design choice to enable
traceability. You can trace, for example, a high temperature reading from
sensor, through the decision that triggered a fan on, to an entry in the audit
database that the fan was activated at a certain time by the automation logic.
This is a common enterprise design pattern for observability in distributed
systems and is being adopted here to ensure the digital twin's actions are
transparent and debuggable.

In summary, the system's architecture patterns emphasize modularity
(microservices, pipeline), reactivity (event-driven pub/sub), and
maintainability (OOP, separation of concerns). These choices align with the
goals of scalability and flexibility. As the project progresses, patterns for
control loops and continuous ML integration will further enrich the system's
design, ensuring that even as complexity grows, the system remains organized
and understandable.

## Data Contracts & Messaging Expectations

Processed sensor payloads extend the raw dataclass with validation flags keyed by
`ValidationFlag`, a 0‒1 data-quality score derived from configured weights, an `imputed`
boolean, and the optional `raw_value` field that preserves the original reading when
imputation or smoothing alters the value emitted to Kafka. The calibration / normalization
pass also attaches the immediate post-calibration reading (`calibrated_value`), the scaled
reading (`normalized_value`), and the profile identifiers applied
(`calibration_profile_id`, `normalization_profile_id`) so downstream consumers can audit
which profile produced each value. Correlation IDs remain mandatory for traceability.

Calibration and normalization strategies are resolved through the config-driven
`ProfileConfiguration` loader and `CalibrationCatalog`. Defaults are keyed by sensor type,
with per-device overrides inheriting any unspecified parameters. Strategies are typed:
calibration currently supports identity, affine, and piecewise lookup transforms, while
normalization supports identity and min-max scaling (with optional clipping). The Spark
pipeline hydrates these strategies per sensor, applies calibration before validation /
imputation, and normalizes the post-validation signal so processed payloads expose raw,
calibrated, and normalized views side-by-side.

### Alerts (`dt/alerts`)
- **Responsibility**: Evaluate rules, manage alert state, and publish lifecycle events.
- **Structure**: Flattened module layout (`api`, `app`, `service`, `registry`, `rules`, `evaluator`, `publisher`).
- **Core Components**:
  - `AlertRegistry`: In-memory state machine (active alerts, cooldowns, persistence). **Hydrates from Database on startup** to restore state after restarts.
  - `RuleEvaluator`: Checks `ProcessedSensorData` against loaded `AlertRule`s.
  - `AlertPublisher`: Persists definitions to DB and publishes `AlertHistoryEvent` to Kafka.
  - `DatabaseApiClient`: Used to fetch active alerts for hydration and upsert definitions.
- **Data Flow**:
  1. Consumes `dt.sensors.processed.*`.
  2. Evaluates rules -> triggers `SensorAlertEvent`.
  3. Updates Registry (checks persistence/cooldown).
  4. If status changes (ACTIVE/CLEARED), publishes to `dt.alerts`.
- **Source of Truth**: 
  - **Historical & Active**: Database Service (via `TimescaleStorage`).
  - **Runtime Logic**: In-memory `AlertRegistry` (synced on startup).
  - **UI Queries**: Dashboard queries Database Service (`/alerts/active`) directly, not the Alert Engine.

### PostgreSQL + TimescaleDB Configuration

The storage layer uses PostgreSQL with the TimescaleDB extension for unified time-series
and relational data storage. Configuration is managed through environment variables with
sensible defaults for local development:

- **PG_DATABASE_URL**: PostgreSQL connection string (default: `postgresql+psycopg://dt:dt@localhost:5432/dt`)
- **SQL_POOL_SIZE**: SQLAlchemy connection pool size (default: 5)

The storage architecture uses SQLAlchemy Core for explicit query control and portability,
avoiding ORM overhead. Hypertables provide automatic time-based partitioning for
measurements, while continuous aggregates maintain 1-hour rollups for
efficient dashboard queries. Compression policies reduce storage footprint for older data
while maintaining query performance.

#### Database Schema

The unified PostgreSQL + TimescaleDB schema consists of:

**Relational Tables:**
- **plants**: Base plant metadata (id, name, notes)
- **sensors**: Sensor configuration with FK to plants (id, plant_id, name, pin, read_interval, status)
- **actuators**: Actuator configuration with FK to plants (id, plant_id, name, relay_channel, status)
- **alert_definitions**: Alert invariants keyed by `(alert_key, plant_id)` with optional sensor FK, source, optional rule_id/rule_name, kind, persistence_count, cooldown_seconds
- **alert_history**: Append-only event log referencing alert_definitions (id PK, alert_key FK, plant_id FK, timestamp, status, severity, message, correlation_id, optional acknowledged_by/acknowledged_ts/cleared_ts)
- **alert_sensors**: Sensor alert snapshots linked to history (id PK, alert_history_id FK, plant_id, sensor_id FK, timestamp, value, unit, topic, correlation_id, flags, dq_score, imputed, raw/calibrated/normalized values, calibration/normalization profiles, threshold_op/threshold_value/range_min/range_max)
- **alert_external**: External alert metadata per history row stored as JSONB (id PK, alert_history_id FK, plant_id, metadata JSONB) — planned move to string key/value rows later

**TimescaleDB Hypertables:**
- **sensor_readings**: Time-series data partitioned by `time` column
  - Fields: time, sensor_id FK, plant_id FK, data_type, value, unit, correlation_id, dq_score, imputed, validation_flag
  - Optional audit fields: raw_value, calibrated_value, normalized_value, calibration_profile_id, normalization_profile_id
  - Retention: 30 days (hardcoded in migration; dynamic configuration planned for future)
  - Compression: Enabled for data >7 days old, segmented by sensor_id, plant_id, data_type (hardcoded in migration)

**Continuous Aggregates:**
- **sensor_readings_1h**: 1-hour rollups (avg, min, max, sample_count, avg_dq_score, imputed_count)
  - Refresh policy: every 30 minutes for last 2 hours of data

#### Schema Migrations

SQL migrations live in `dt/data/database/migrations/` and are executed in alphanumeric order by the database service on startup (`dt/data/database/app.py`). The migration runner tracks applied migrations in the `schema_migrations` table to ensure idempotency.

The migrations directory can be overridden by setting `DB_MIGRATIONS_DIR`.

**Running Migrations:**
```bash
# Ensure PG_DATABASE_URL is configured in .env
python scripts/run_sql_migration.py
```

The runner uses `psycopg` to execute each `*.sql` file and records completion in `schema_migrations`. Future schema changes should be added as new numbered migration files (e.g., `002_add_experiments_table.sql`).

**Design Choice:** Alerts are modeled as append-only history events keyed by `(alert_key, plant_id)` with sensor snapshots and external metadata attached per event. Thresholds live on sensor snapshots; external metadata is temporarily stored as JSONB with a planned move to key/value rows.

#### TimescaleDB Policies & Continuous Aggregates

TimescaleDB policies (retention and continuous aggregates) are defined directly in the `001_init.sql` migration for the `sensor_readings` Hypercore hypertable. Current configuration:

- **Retention**: 30 days for raw measurements (migration-defined).
- **Compression**: Hypercore columnstore options are set on the hypertable; Data moved to Columnarstorage after 7 days.
- **Continuous Aggregates**: 1-hour rollups with refresh every 30 minutes over the last 2 hours.
- **5-minute aggregates**: Removed for now; add later if the dashboard needs finer granularity.

Policies are hardcoded in the migration for deterministic schema setup. If we need adjustable policies later, add a configuration interface and avoid duplicating policy statements between migrations and runtime scripts.

### Alert Service REST API

The alert engine exposes a REST API (default port 5003) for programmatic alert management:

**Alert Management Endpoints:**
- `POST /alerts/submit` — Submit external alerts (e.g., from AI/control modules)
  - Required fields: `alert_key`, `plant_id`, `severity`, `message`, `correlation_id`
  - Optional fields: `metadata` (dict), `persistence_count` (default: 1), `cooldown_seconds` (default: 300)
  - Returns: 202 Accepted with `alert_key` and `status` (`active` or `ignored` when persistence/cooldown suppresses publishing)

- `POST /alerts/<alert_key>/acknowledge` — Acknowledge an alert
  - Required body: `{"actor": "<identifier>"}`
  - Looks up registry state by `alert_key` (propagates plant_id/source/severity/message/correlation_id) and publishes `ACKNOWLEDGED` history event with minimal payload
  - Returns: 200 OK on success, 404 if alert not found
  - Publishes `ACKNOWLEDGED` event to Kafka

- `POST /alerts/<alert_key>/clear` — Clear a resolved alert
  - Uses registry state to propagate plant_id/source/severity/message/correlation_id and publishes a minimal `CLEARED` history event
  - Returns: 200 OK on success, 404 if alert not found
  - Publishes `CLEARED` event to Kafka

- `GET /alerts/active` — List all active alerts
  - Returns: JSON array of active alert states with timestamps, severity, acknowledgment status, and occurrence counts

**Configuration Endpoint:**
- `GET /alert-rules` — Retrieve configured alert rules
  - Returns: JSON array of all loaded alert rule definitions

All REST operations that modify alert state (submit, acknowledge, clear) publish corresponding
lifecycle events to the `dt.alerts` Kafka topic for downstream consumers (dashboard, audit logger, notification workers).

## Preprocessing Pipeline Architecture

The preprocessing module (`dt/data/preprocess`) uses a **Chain of Responsibility**
pattern to process sensor data through multiple stages. This modular design supports
the project requirement for extensibility and maintainability.

### Pipeline Structure

The pipeline processes readings through five stages:

1. **Calibration**: Apply sensor-specific calibration transformations
2. **Validation**: Check range, rate-of-change, and stuck values
3. **Imputation**: Replace invalid values using configured strategies
4. **Smoothing**: Apply noise reduction filters (EWMA, pass-through)
5. **Normalization**: Scale values to standard range [0, 1]

Each stage is implemented as a `BaseProcessor` subclass that receives a
`ProcessingContext`, performs its operation, and returns the updated context.

### Key Components

- **ProcessingContext**: Mutable dataclass carrying all state through the pipeline
- **BaseProcessor**: Abstract interface enforcing the processor contract
- **ProcessingPipeline**: Chain executor running processors in sequence
- **ConfigurationManager**: Centralized config loading and strategy caching
- **PipelineBuilder**: Factory for creating configured pipelines
- **SparkStreamingAdapter**: Isolates Spark-specific concerns from business logic

### Extensibility

Adding a new processing step requires:

1. Create a class inheriting from `BaseProcessor`
2. Implement the `process(context)` method
3. Add the processor to `PipelineBuilder`

Example:

```python
class AnomalyDetectionProcessor(BaseProcessor):
    def process(self, context: ProcessingContext) -> ProcessingContext:
        # Detect anomalies in context.smoothed_value
        context.is_anomaly = self._detect(context.smoothed_value)
        return context

# In PipelineBuilder:
pipeline.add_processor(AnomalyDetectionProcessor())
```

### Testing Strategy

- **Unit tests**: Each processor tested independently with mocks
- **Integration tests**: Full pipeline tested with real strategies
- **Spark isolation**: Business logic is Spark-agnostic and testable without SparkSession

## Coding Standards & Practices

The codebase follows standard **Python coding conventions** (PEP8 style for
naming, formatting, etc.) and is organized for clarity. Early in the project, a
consistent repository structure was established: all code resides under a dt/
package with clear sub-packages for each module (data/, ai/, webapp/, utils/,
etc.), as outlined in the kickoff phase. This structure makes it easy to
navigate the project and locate relevant code (for example, anything related to
data processing is in dt/data/...). Configuration is managed via a central
**config file and environment variables** (a .env file and config.py) to
avoid hard-coding parameters and credentials. This means things like database
URLs, API keys, sensor calibration constants, etc., can be changed in one place
without modifying the code, adhering to the **12-factor app** principles for
config separation.

**Dependency management** is handled with Poetry (as mentioned), which ensures
that all contributors or deployments use the same library versions. The project
likely includes a pyproject.toml with pinned versions, and a lockfile for
reproducibility. This is complemented by environment spec
for deploying on the Raspberry Pi (making use of Poetry's export or the extras
groups defined for raspi, spark, dev to install appropriate subsets of
packages). Ensuring the Pi doesn't install heavy dev or Spark libraries unless
needed was a thought-out step, indicating a mindful approach to environment
management.

In the current phase, the project introduced unit tests to verify that each
module performs as expected.  Already in the preprocessing phase, unit tests
were planned for schema validation and other functionalities. The code includes
test cases (using **pytest**) to verify that each module performs as expected
(e.g., does the missing-data handler fill gaps correctly? Do alerts fire under
the right conditions?). 

Currently, the project utilizes Python's built-in `logging` package for
application logs. While logs are not yet structured in JSON or unified by a
correlation ID, the codebase could follow a more advanced logging
strategies in the future. 

**Documentation** and contributor guidelines are treated seriously. The roadmap
indicates deliverables such as CONTRIBUTING.md and technical documentation
(e.g., preprocessing-spec.md, an alert catalog, etc.). This means the code
likely contains docstrings (numpydoc-style) and comments where complex logic
occurs, and the repository includes markdown docs for setup instructions,
design decisions, and how to contribute/test. Adhering to these documentation
standards ensures new contributors (or the future self) can understand the code
and system design without guesswork.

In coding style, one can infer that the project values clarity and
maintainability. Functions and classes are probably kept concise, following
single-responsibility principle (since each service itself has a single
responsibility, and within a service, components likely mirror that). The use
of type hints in Python could be present to improve code clarity and catch type
errors. 

Finally, the project integrates **DevOps practices** like using a Makefile for
common operations (as seen in the installation instructions). This provides a
simple interface to run the system (make main, make web, make db, etc.) and can
enforce running things like linters or tests via make targets. Continuous
deployment isn't currently implemented (since this is a prototype), but the
groundwork (unit tests) sets the stage for easy deployment when the time comes.

In summary, the coding standards revolve around **maintainability, and
reliability**: a clean project structure, thorough documentation, environment
consistency, rigorous testing, and logging/monitoring to know what's happening
internally. These practices ensure that the digital twin system can be
confidently extended and used, aligning with the goal of a reproducible and
high-quality outcome.
