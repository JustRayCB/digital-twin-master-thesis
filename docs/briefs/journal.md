# Engineering Journal (append-only)
## <YYYY-MM-DD> — <topic>
- Hypothesis:
- Experiment:
- Result:
- Decision:
- MEM-DRIFT: <doc vs code> (propose PR to <file>)
## 2025-10-08 — Preprocessing pipeline kickoff
- Hypothesis: The preprocessing implementation plan aligns with current active context; assume preprocessing_config.yml provides complete rule thresholds.
- Experiment: Reviewed the data preprocessing module plan to capture required tasks and conventions before writing tests.
- Result: Plan understood; need to verify memory bank entries and config details prior to deeper implementation.
- Decision: Proceed with Task 1 by establishing test scaffolding while tracking outstanding questions on rule weights.
- Open questions: Confirm source of canonical DQ weight values and whether sample sensor configs exist for tests.
- MEM-DRIFT: none
## 2025-10-12 — Imputation strategy defaults
- Hypothesis: Forward fill with exponential decay provides stable imputation using last valid readings and configurable baselines.
- Experiment: Drafted unit and decay-focused tests exercising long and short gaps, then implemented a ForwardFillWithDecay strategy plus factory.
- Result: Tests confirm decay toward baseline and baseline fallback when the gap exceeds limits; factory defends against unsupported strategies.
- Decision: Adopt configurable decay (max_gap_seconds, decay_seconds, optional baseline) with safe defaults when sensor config omits imputation settings.
- MEM-DRIFT: none
## 2025-10-14 — Windowed imputation
- Hypothesis: DHT22 and BH1750 readings benefit from local averaging; decay-only fill leaves short-term noise untouched.
- Experiment: Enabled window_average strategy in sensor config, trimmed state history after each window query, ran targeted state/imputer tests; split imputation configs per strategy and added linear extrapolation scaffolding.
- Result: Config-driven averaging applied per sensor with deterministic state bounds validated by unit suite; smoothing registry now supports pass-through and EWMA implementations; imputation loader now returns typed configs (forward fill, window average, linear extrapolation).
- Decision: Tune to sampling rates — DHT22 (2 min) uses 6-minute window (min 2 samples), BH1750 (1 min) uses 3-minute window (min 3 samples), soil moisture (2 min) uses forward fill with 10-minute max gap and gentle decay window; EWMA smoothing (alpha configurable) available alongside pass-through default; linear extrapolation ready for sensors that need it.
- MEM-DRIFT: none
## 2025-10-23 — Spark state serialization failure
- Hypothesis: Structured streaming tests crash because `SparkStateProvider` writes dictionaries to `GroupState.update`, which expects tuples matching the declared schema.
- Experiment: Reproduced failure locally, inspected PySpark `GroupState.update` implementation, and simulated schema conversion via `SensorState.get_spark_schema().toInternal`.
- Result: Confirmed dict input becomes row of keys (`'last_valid'`, etc.), triggering `[UNEXPECTED_TUPLE_WITH_STRUCT]` during state persistence; migrating the dataclasses to emit tuple-native payloads keeps serialization compatible.
- Decision: Make `SensorState` / `FlatlineRecord` store tuples directly, have `SparkStateProvider` read/write raw tuples, and ensure `RawSensorData` tuple helpers produce primitive values so Kafka topics survive pickling.
- MEM-DRIFT: none
## 2025-10-24 — Streaming edge cases hardening
- Hypothesis: Unknown sensors, late arrivals, and imputation gaps can surface in real Structured Streaming; 
- Experiment: Added event-time watermarks with state timeouts, persisted raw last-valid readings, logged unknown sensors while dropping their payload, captured raw sensor values when outputs are imputed/smoothed, and extended structured-streaming tests.
- Result: Pipeline now skips unregistered sensors with a warning, keeps executor state bounded thanks to timeouts, and enriches processed events with `raw_value` when the published value differs. Streaming tests validate range/ROC/stuck failures, missing history, and unknown-sensor behaviour. 
- Decision: Ship with logging + drop behaviour for unknown sensors, keep raw values as the persisted state anchor, and defer explicit alert/QoS surfaces until the UI is ready.
- MEM-DRIFT: none
## 2025-10-26 — Preprocessing documentation sync
- Hypothesis: Memory bank and README lacked explicit coverage of preprocessing pipeline contracts; aligning them prevents drift while Task 10 lands.
- Experiment: Reviewed preprocessing modules, then updated active context, system patterns, progress, todo, and README sections to document validators, state provider usage, imputation, smoothing, and remaining work.
- Result: Documentation reflects the streaming job structure, processed payload contents, and upcoming priorities (calibration, alerts, Kalman evaluation).
- Decision: Track Kalman smoothing feasibility and audit/action store design as near-term follow-ups.
- MEM-DRIFT: docs/briefs/systemPatterns.md missing StateProvider and processed payload contract details → updated docs/briefs/systemPatterns.md
## 2025-10-27 — Calibration profile config schema
- Hypothesis: Calibration and normalization defaults can live in the preprocessing config with partial per-sensor overrides merged at load time.
- Experiment: Wrote config loader unit tests that expect merged defaults/overrides, then implemented loader dataclasses plus YAML sections and reran the focused suite.
- Result: Loader returns typed collections where overrides inherit unspecified parameters from the defaults; validation catches missing sensor types.
- Decision: Adopt `ProfileConfiguration` bundle so the upcoming catalog can serve per-sensor calibration and normalization strategies with profile IDs intact.
- MEM-DRIFT: docs/briefs/systemPatterns.md lacks calibration/normalization profile wiring → update during Task G documentation pass.
## 2025-10-27 — Calibration catalog resolver
- Hypothesis: A catalog layered on the profile loader can deliver per-sensor calibration/normalization data if we map sensor IDs to sensor types.
- Experiment: Added catalog unit tests covering override precedence, default fallback via explicit registration, and missing sensor handling; built the `CalibrationCatalog` around the loader outputs with a registration API.
- Result: Catalog now serves profile definitions, seeds override sensor types automatically, and raises when callers forget to register non-overridden sensors.
- Decision: Use catalog registration wherever the pipeline resolves sensor configs so calibration lookups share the same identifiers.
- MEM-DRIFT: same as prior entry — document profile + catalog workflow in systemPatterns during Task G.
## 2025-10-27 — Calibration & normalization strategies
- Hypothesis: Strategy classes mirroring imputation/smoothing patterns can cover identity, affine, piecewise lookup, and min-max scaling needs.
- Experiment: Wrote unit tests for affine defaults, piecewise lookup edge cases, and normalization clamping/extrapolation; implemented strategy base classes plus builders that validate parameters.
- Result: Strategies now construct from `ProfileDefinition`, enforce required parameters, and deliver deterministic outputs for our active sensors.
- Decision: Reuse these builders when wiring the catalog into the Spark pipeline so calibration and normalization stay config-driven.
- MEM-DRIFT: same as earlier — add calibration/normalization strategy description to systemPatterns in Task G.
## 2025-10-27 — Profile parameter typing
- Hypothesis: Replacing dict-based profile parameters with typed dataclasses would remove magic strings and keep overrides type-safe.
- Experiment: Refactored the config loader to hydrate strategy-specific parameter dataclasses, adjusted merges for overrides, and updated catalog/strategy builders plus tests.
- Result: Affine, piecewise lookup, and min-max parameters are now strongly typed end-to-end; loader validation still catches missing fields early.
- Decision: Maintain the typed parameter union going forward so future strategies plug in with explicit config shapes.
- MEM-DRIFT: same outstanding systemPatterns update to document the typed profile flow.
## 2025-10-27 — Catalog reload support
- Hypothesis: Exposing a reload hook on the calibration catalog prevents config drift when we hot-swap profile files later.
- Experiment: Added `CalibrationCatalog.reload`, reset override seeding to overwrite outdated mappings, and extended tests to confirm registrations persist unless a new map is provided.
- Result: Catalog can refresh both profiles and sensor mappings in place; override lookups pick up new profiles immediately.
- Decision: Wire the reload path into Spark pipeline config watch once Task D lands so streaming jobs can adopt updated profiles without restart.
- MEM-DRIFT: document catalog reload semantics in systemPatterns during Task G.
## 2025-10-28 — Calibration normalization harness
- Hypothesis: A Spark-backed integration test will prove calibration and normalization profiles are wired correctly before we extend streaming jobs.
- Experiment: Built `tests/data/preprocess/test_end_to_end_calibration.py` using the existing pipeline helpers, configured default and override profiles, and asserted raw/calibrated/normalized values plus profile IDs.
- Result: Test passes with current pipeline implementation; confirms calibration runs before validation and normalization emits expected scaled values.
- Decision: Use the harness as regression coverage while wiring catalog refresh and additional profile scenarios.
- MEM-DRIFT: docs/briefs/systemPatterns.md now documents calibration and normalization strategy flow.
## 2025-10-31 — Preprocessing pipeline refactoring
- **Context**: The monolithic `pipeline.py` (942 lines) was becoming hard to read, test, and extend. Project requirements emphasize modularity and extensibility. Growing complexity with calibration, normalization, validation, imputation, and smoothing all in one file made maintenance difficult.
- **Decision**: Refactor into Chain of Responsibility pattern with five processors: Calibration → Validation → Imputation → Smoothing → Normalization.
- **Approach**:
  - Created `ProcessingContext` dataclass for shared state
  - Defined `BaseProcessor` abstract interface
  - Implemented five processor classes, each with single responsibility
  - Consolidated config/strategy management into `ConfigurationManager`
  - Built `ProcessingPipeline` chain executor and `PipelineBuilder` factory
  - Isolated Spark logic in `SparkStreamingAdapter`
  - Followed TDD throughout: write test first, implement, then commit
- **Result**: Successfully refactored pipeline into modular architecture. All existing tests pass. New unit tests cover new code. Integration test validates end-to-end behavior. Spark isolation enables testing without SparkSession.
- **Tradeoffs**: Added more classes (was 1 file, now 10+ files in `dt/data/preprocess/pipeline/`), but each is focused and testable. Initial learning curve for understanding chain pattern, but clearer once grasped. More files to navigate but better separation of concerns.
- **Future considerations**: Could explore hot-reload for config changes.
- MEM-DRIFT: docs/briefs/systemPatterns.md updated with preprocessing pipeline architecture section.
## 2025-10-31 — Preprocessing package reorg
- Context: Configuration dataclasses and strategy helpers lived under `dt/communication` or flat modules, making the preprocessing boundary messy.
- Decision: Move sensor/config dataclasses and profile loaders into `dt/data/preprocess/configuration`, split validators/imputers/smoothing/dq into packages, isolate normalization strategies away from calibration, lift processors into a dedicated `processors/` namespace, and host state models/providers under `dt/data/preprocess/state/`.
- Result: Preprocessing module now groups configuration, processors, and strategies by concern; imports updated and unit suites green (Spark-dependent tests noted for follow-up).
- MEM-DRIFT: Still need to audit `docs/briefs/systemPatterns.md` for any lingering references to the old module layout in the next documentation pass.
## 2025-10-31 — Legacy pipeline removal
- Context: Modular preprocessing pipeline has been stable through calibration/normalization work; legacy `pipeline_legacy.py` was kept only as a fallback.
- Decision: Drop the deprecated legacy module to avoid dual-maintenance and prevent accidental reuse.
- Result: Deleted `dt/data/preprocess/pipeline_legacy.py`, scrubbed documentation references, and retained the modular `SparkStreamingAdapter` flow as the single source of truth.
- MEM-DRIFT: docs/briefs/progress.md updated; no other drift observed.
## 2025-11-01 — Alert engine service introduction
- Context: Preprocessing delivers validated, calibrated, and normalized sensor data via `dt.sensors.processed.*` topics. Alerting logic is currently absent; multiple modules would duplicate threshold checks without a central authority.
- Decision: Introduce a dedicated `dt.alerts` service that (1) subscribes to processed sensor topics and evaluates configured rules, (2) exposes REST endpoints for programmatic alert submission, acknowledgment, clearing, and listing, (3) maintains in-memory alert state (deduplication, persistence counters, cooldown timers, acknowledgment flags), and (4) publishes canonical `AlertEvent` payloads to `dt.alerts.*` for downstream consumers (dashboard, audit log, notification workers).
- Approach: Follow TDD implementation plan in `docs/plans/alert_engine_implementation_plan.md` across 12 phases, building config layer (YAML rules + loader), rule evaluator (threshold/range/dq/flag conditions), in-memory registry (lifecycle tracking), REST API (Flask blueprint), Kafka publisher (MessagingService wrapper), Kafka consumer (processed topics → evaluator), and application wiring (create_app factory).
- Goal: Deliver MVP alert engine with rule-based evaluation, manual submissions, persistence/cooldown logic, and Kafka publishing; defer database persistence (document hook points only).
- MEM-DRIFT: none detected; existing `AlertEvent` dataclass and processed payload contracts align with plan.
## 2025-11-02 — Alert rule manager & payload context
- Context: While wiring the alert engine configuration, validation logic in the YAML loader started to duplicate enum coercion and required-field checks already implied by the dataclasses. The evaluation helper also mirrored `ProcessedSensorData` structure manually.
- Decision: Move `from_dict`/`override` logic into `AlertRule` and `AlertCondition`, expose an `AlertRuleManager` that delegates parsing to those helpers, and default the rules file to `dt/utils/alert_rules.yml`. Simplify the processed payload adapter by relying on `dataclasses.asdict(processed)` plus the topic short name instead of custom field extraction.
- Result: Configuration parsing is centralized with the dataclasses, override behaviour is reusable in tests and runtime, and the evaluation adapter stays aligned with `ProcessedSensorData` without manual field lists. Updated implementation plan and documentation to reference the manager and the new config path.
- MEM-DRIFT: docs/plans/alert_engine_implementation_plan.md updated; no additional drift noted.
## 2025-11-03 — Alert engine service design
- **Context**: Need centralized alert management to prevent duplicate/conflicting alerts from multiple modules (AI, control, preprocessing). Alert fatigue is a real concern - operators need meaningful alerts, not notification spam.
- **Hypothesis**: An event-driven alert service consuming processed sensor data and maintaining authoritative alert state will provide consistent alerting across the system. Persistence counters and cooldown timers can prevent alert fatigue without losing signal.
- **Design decisions**:
  1. **Alert ID Strategy**: Rule-based alerts use `{rule_id}:{source}` format for deterministic deduplication across sensor streams. External submissions (AI, control) provide custom IDs for tracking. This ensures each alert condition has exactly one active alert per source.
  2. **Persistence Mechanism**: Require N consecutive violations before creating alert (configurable per rule). Prevents transient spikes from generating alerts. Counter resets if condition clears, ensuring we only alert on sustained problems.
  3. **Cooldown Timers**: After alert fires, suppress repeated alerts for configurable cooldown period (default 300s). Once cooldown expires, alert can fire again if condition persists. Acknowledgments don't prevent future alerts - they're informational state only.
  4. **In-Memory State**: Registry maintains alert state in memory for fast lookups and updates. Trade-off: state lost on restart, but gain simplicity and speed for MVP. Database persistence layer planned for audit/action store phase.
  5. **Lifecycle Events**: Publish alert history with `AlertStatus` (ACTIVE for creates/updates, ACKNOWLEDGED, CLEARED) to Kafka for audit trail and downstream consumption; IGNORED (cooldown/persistence cases) is not published to reduce noise.
  6. **REST API Design**: Separate endpoints for submission (POST /alerts/submit), acknowledgment (POST /alerts/<id>/acknowledge with actor), clearing (POST /alerts/<id>/clear), and listing (GET /alerts/active, GET /alert-rules). API accepts external submissions from AI/control modules, enabling them to raise alerts without duplicating logic.
  7. **Configuration Format**: YAML-based rules with typed validation (severity, condition types, evaluation stages). Support 4 condition types for MVP: threshold (with operators), range (min/max bounds), dq_score, validation_flag. Easy to extend with new condition types later.
- **Result**: Implemented `dt.alerts` package with 122 passing tests. Full TDD approach: rule loader, evaluator, registry, publisher, API, consumer service, and integration tests. Service successfully evaluates rules against processed sensor streams and maintains alert state with persistence/cooldown logic.
- **Trade-offs**:
  - In-memory state means restart clears alerts (acceptable for MVP; persistence layer planned)
  - Cooldown applies per alert_id, not globally - could still get alert fatigue if many different rules trigger (acceptable; operators can adjust rule sensitivity)
- **Future considerations**:
  - Add database persistence layer for alert history and recovery after restart
  - Consider time-windowed aggregations (e.g., "3 violations in 10 minutes" vs "3 consecutive violations")
  - Add notification workers consuming dt.alerts topic (email, SMS, push notifications)
  - Wire alert service into dashboard UI for real-time display and acknowledgment
- MEM-DRIFT: none
## 2025-11-05 — Storage architecture overhaul kickoff
- Hypothesis: A unified PostgreSQL + TimescaleDB storage layer with explicit SQL migrations will simplify operations and support time-series features while preserving flexibility.
- Experiment: Assessed DB choice and architecture (TimescaleStorage and migrations). Identified risks (Pi resources, schema evolution, aggregate refresh timing, Influx cutover) and documented mitigations.
- Result: Architecture and risk profile validated; forward-only versioned SQL approach selected with a lightweight runner and history table.
- Decision: Proceed with TDD phases from the storage plan; run manual SQL migrations via the runner during deploy; install PG/Timescale on the Pi.
- MEM-DRIFT: none
## 2025-11-05 — Bootstrap Timescale and refactor service bootstrap
- Hypothesis: Introducing an app factory and dependency-injected storage will make the DB service testable and ready for Timescale without side effects.
- Experiment: Added PG/Timescale setup script; created `timescale_storage.py` skeleton with injected engine; wrote smoke tests for `create_app`; refactored `app.py` to `create_app` + `setup_bridge`; made Influx optional to decouple tests.
- Result: All bootstrap tests pass; Flask routes register via the factory; storage injection works; Kafka bridge setup is isolated.
- Decision: Adopt factory + DI pattern for the database service and continue to Phase 3 with Timescale-focused work.
- MEM-DRIFT: none

## 2025-11-08 — Phase 3: Normalized schema design for alert events
- Hypothesis: Normalizing alert event context and omitting `event_type` and audit timestamps will improve extensibility and clarity without losing information.
- Experiment: Authored `001_init.sql` with normalized relations and hypertable/aggregates/policies; implemented `MigrationRunner` and CLI; updated system patterns; fixed SQL syntax; registered pytest marker; propagated `plant_id` through SensorDescriptor and call sites.
- Result: Migrations run cleanly; schema stands up; tests are pristine; ready to implement the repository in Phase 4.
- Decision: Adopt the normalized alert schema; keep `event_type`/created/updated timestamps out; proceed to repository implementation next.
- MEM-DRIFT: Plan updated to reflect normalized schema; `systemPatterns.md` documents the schema and migration process.

## 2025-11-25 — Storage architecture completed (PostgreSQL + TimescaleDB)
- **Context**: Two-database overhead (Influx + planned SQL) was too high; needed unified storage with a managed-DB path.
- **Hypothesis**: PostgreSQL + TimescaleDB can handle time-series and relational data with manageable ops.
- **Experiment**: Added PG/Timescale config; enabled Timescale; defined schema in `001_init.sql` (Hypercore `sensor_readings`, 1h CAGG, retention); built `TimescaleStorage`; expanded REST (readings/sensors/actuators/alerts); Kafka bridge persists measurements and alerts; dropped policy tooling; updated docs; ran full tests.
- **Result**: Unified PG/Timescale storage in place; tests pass; simple Flask→storage wiring with pooling.
- **Decisions**: 1h CAGG only; policies fixed in migration (Hypercore set, no scheduled columnstore policy); keep direct storage calls (db service later if needed); alert schema stays normalized.
- **Trade-offs**: 1h-only aggregates; policies hardcoded; direct coupling acceptable now.
- **Migration path**: Point `PG_DATABASE_URL` to managed PG; reuse schema; document backup/restore later.
- MEM-DRIFT: Docs updated; plan marked Phase 8 complete.

## 2025-11-30 — Alert definitions persisted before publishing
- Context: Alert engine definition alignment (Task 2) needed pre-publish persistence for both sensor and external alerts.
- Decision: RuleEvaluator now returns (AlertDefinition, AlertEvent) tuples; publisher persists definitions via the database API `/alerts/definitions` (DatabaseApiClient) before sending Kafka events; external/ACK/CLEAR paths build definitions too; storage guard remains as a safety net.
- Result: Added DB API endpoint for idempotent definition upserts; AlertPublisher gates publish on successful definition persistence; tests updated across evaluator, publisher, API, registry flows.
- MEM-DRIFT: Documented in `systemPatterns.md` (definition upsert contract and `/alerts/definitions` endpoint).
## 2025-12-02 — Alert API contract alignment
- Hypothesis: The REST surface should mirror the alert_key + plant_id contract used by the alert engine and Kafka payloads to avoid drift across services.
- Experiment: Reviewed submit/ACK/CLEAR flows and synchronized tests to the minimal AlertHistoryEvent payload (ack/clear) and alert_key-based submissions with persistence/cooldown validation.
- Result: API tests now assert alert_key, plant_id, correlation_id propagation for ACK/CLEAR; integration flow verifies reading snapshots on sensor events; REST docs refreshed to match the contract.
- Decision: Keep ACK/CLEAR payloads minimal (no metadata) and rely on registry state to populate plant_id/source/severity/message/correlation_id; treat persistence/cooldown validation as part of submit.
- MEM-DRIFT: Updated `systemPatterns.md` REST API section to match the alert_key-based contract.

## 2025-12-24 — Database service runs SQL migrations on startup
- Context: DB schema initialization relied on `scripts/run_sql_migration.py`, but the database service could be started without applying migrations.
- Decision: Run `MigrationRunner` automatically on database service startup and stop the service on migration failure.
- Rationale: Minimize operator steps and prevent the service from running against an uninitialized schema.
- MEM-DRIFT: `systemPatterns.md` and `README.md` must reflect startup migrations as the default path (runner remains available for manual use).

## 2025-12-25 — Circular import in preprocessing config tests
- Hypothesis: Import-time side effects in package `__init__.py` and cross-layer adapter hooks create a circular import between `dt.communication` and `dt.data.preprocess`.
- Experiment: Reproduced failure by importing `dt.communication.adapters` and `dt.data.preprocess.config.manager`; traced the cycle through `dt/communication/__init__.py`, adapter registry eager instantiation, and `dt/data/preprocess/core/__init__.py` re-exports.
- Result: Confirmed two root causes: (1) package `__init__.py` files importing heavy submodules at import time, and (2) `GenericAdapter` importing preprocessing config types to register structure hooks.
- Decision: Keep `dt/communication/__init__.py`, `dt/data/preprocess/core/__init__.py`, and `dt/data/preprocess/config/__init__.py` import-free; move preprocessing config structure-hook registration into `dt.data.preprocess.config.serialization` and call it from `ConfigurationManager` before parsing YAML.
- MEM-DRIFT: none

## 2025-12-25 — Preprocessing pipeline config/schema alignment
- Context: Preprocessing tests failed after the refactor to the unified preprocessing YAML schema and modular pipeline.
- Root cause: The code and tests still referenced removed modules (`dt.data.preprocess.config.profiles`, `...config.preprocessing_config`, `...configuration.preprocessing_config`) and several processors still assumed the old `SensorConfig` shape (top-level `range/roc/stuck`) and old `ConfigurationManager` strategy APIs.
- Fix: Added `IdentityCalibrationConfig` to the config schema and serialization hooks so `strategy: identity` loads correctly; updated validation/imputation/smoothing processors to use the new schema (`sensor_config.validation.*`) and current `ConfigurationManager` strategy methods; updated tests to match the new architecture.
- Result: `pytest -m "not requires_timescale"` is green locally; TimescaleDB integration tests still require Docker access.
- MEM-DRIFT: none

## 2025-12-27 — Split Kafka bridge out of webapp app
- Context: `dt/webapp/app.py` was accumulating Kafka bridge and payload-shaping logic alongside Flask app wiring.
- Decision: Extract Kafka subscription and Socket.IO forwarding logic (plus payload shaping and cache helpers) into `dt/webapp/consumer.py`; keep Flask/Socket.IO app creation and connection handlers in `dt/webapp/app.py`.
- Result: Webapp tests remain green after the refactor.

## 2025-12-27 — Best-effort scheduling for collector loop
- Context: `dt/collector/main.py` polled in a tight loop with a fixed sleep, even though sensors have independent `read_interval` values.
- Root cause: Collector scheduling was not using next-due timing; additionally, importing `dt.collector` in a non-RPi environment failed due to eager `board` imports and a stale `SensorData` type import in `SensorManager`.
- Decision: Add a best-effort scheduler (`SensorManager.seconds_until_next_read`) and make collector imports lazy when `board` is unavailable so unit tests can run off-device.
- Result: `dt/collector/main.py` now sleeps until the next sensor is due; added unit tests for scheduling without requiring Kafka/DB connections.
- Notes: Ray approved skipping GitHub issue/PR linking for this task.
## 2025-12-27 — Alert tests cleanup approach
- Hypothesis: Standardizing alert tests around real classes and shared fixtures will keep intent clear while reducing mocks and duplication.
- Experiment: Drafted testing guidelines and refactored `tests/alerts/` to use real registry/evaluator/publisher behavior with small fakes at boundaries.
- Result: Alert tests now rely on shared fixtures and recording fakes for Kafka/publishing, with NumPy-style docstrings and clearer assertions.
- Decision: Continue folder-by-folder test refactors using the same pattern and update guidelines as needed.
- MEM-DRIFT: none
## 2025-12-27 — Alert tests with container-backed dependencies
- Hypothesis: Replacing alert test fakes with Kafka/PostgreSQL containers will better reflect production behavior and align with testing guidelines.
- Experiment: Updated alert tests to use Kafka and TimescaleDB testcontainers, a live database service, and Kafka consumers for assertions.
- Result: Alert API, publisher, service, and integration tests now exercise real Kafka publishing and definition persistence with fewer test doubles.
- Decision: Prefer container-backed fixtures for alert tests that cross service boundaries; keep pure unit tests for rules/registry.
- MEM-DRIFT: none
## 2025-12-28 — Adapter test refactor guidelines
- Hypothesis: Consistent docstrings, fixtures, and comments will improve test clarity without changing behavior.
- Experiment: Added docs/testing.md guidelines, refactored tests/communication/adapters with shared fixtures and clearer assertions, and ran targeted pytest.
- Result: Adapter tests are more readable and reusable; pytest `tests/communication/adapters` passed (60 tests).
- Decision: Apply the guidelines folder-by-folder, starting with adapters and continuing with remaining test suites.
- MEM-DRIFT: none
## 2025-12-28 — Storage backend documentation drift
- Hypothesis: Storage backend references should align across briefs and code.
- Experiment: Reviewed `dt/data/database` implementation and compared `docs/briefs/projectbrief.md` with `docs/briefs/systemPatterns.md` and `docs/briefs/techStack.md`.
- Result: `docs/briefs/projectbrief.md` still references InfluxDB, while code and other briefs describe PostgreSQL + TimescaleDB.
- Decision: Propose updating `docs/briefs/projectbrief.md` to reflect PostgreSQL + TimescaleDB as the storage backend.
- MEM-DRIFT: `docs/briefs/projectbrief.md` storage section mentions InfluxDB vs current PostgreSQL + TimescaleDB (propose PR update to `docs/briefs/projectbrief.md`).
