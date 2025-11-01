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
## 2025-11-01 — Preprocessing package reorg
- Context: Configuration dataclasses and strategy helpers lived under `dt/communication` or flat modules, making the preprocessing boundary messy.
- Decision: Move sensor/config dataclasses and profile loaders into `dt/data/preprocess/configuration`, split validators/imputers/smoothing/dq into packages, isolate normalization strategies away from calibration, lift processors into a dedicated `processors/` namespace, and host state models/providers under `dt/data/preprocess/state/`.
- Result: Preprocessing module now groups configuration, processors, and strategies by concern; imports updated and unit suites green (Spark-dependent tests noted for follow-up).
- MEM-DRIFT: Still need to audit `docs/briefs/systemPatterns.md` for any lingering references to the old module layout in the next documentation pass.
## 2025-11-03 — Legacy pipeline removal
- Context: Modular preprocessing pipeline has been stable through calibration/normalization work; legacy `pipeline_legacy.py` was kept only as a fallback.
- Decision: Drop the deprecated legacy module to avoid dual-maintenance and prevent accidental reuse.
- Result: Deleted `dt/data/preprocess/pipeline_legacy.py`, scrubbed documentation references, and retained the modular `SparkStreamingAdapter` flow as the single source of truth.
- MEM-DRIFT: docs/briefs/progress.md updated; no other drift observed.
