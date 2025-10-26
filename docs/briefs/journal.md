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
