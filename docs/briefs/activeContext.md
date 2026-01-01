# Active Context
**Branch:** <feature/...>
**Phase:** P<1-4>
**Window:** <YYYY-MM-DD → YYYY-MM-DD>

## Focus & Exit Criteria
- Focus: <one sentence>
- Exit: <bullet, measurable>

## Near-Term Tasks (this sprint)
- [ ] <task> (owner, link-to-issue)
- [ ] <task> …

## Changes Since Last Update
- <one-liners of scope/config/pattern changes>

## Risks/Blockers (with mitigations)
- <risk> → <mitigation>


# Active Context
**Branch:** feature/storage-architecture
**Phase:** P1 — Data Preprocessing & Quality
**Window:** Oct–Dec 2025

---

## 🎯 Focus & Exit Criteria
**Focus:** Build a production-ready real-time preprocessing pipeline ensuring sensor data validity, integrity, and readiness for analytics.
**Exit criteria (target Dec 2025):**
- Data validation gates (range, rate, stuck, flatline) ≥ 99% pass rate
- DQ score and alerting active in dashboard
- Schema versioning and audit log stable
- TimescaleDB retention & aggregates automated ✅
- Basic alerting rules engine functional ✅
- Action logging schema and API endpoints defined

---

## 🧩 Near-Term Tasks (This Sprint)
- [x] Define and implement sensor event schema
- [x] Sensor data validation pipelines/rules (range, RoC, stuck or flatline, DQ scoring)
- [x] Implement missing data handling (forward fill, window averaging, linear extrapolation guardrails)
- [x] Refactor monolithic pipeline.py into modular architecture (feature/pipeline-refactoring → feature/calibration-normalization-pipeline)
  - Chain of Responsibility pattern with 5 processors (Calibration → Validation → Imputation → Smoothing → Normalization)
  - See docs/plans/pipeline_refactoring_implementation_plan.md for full plan
- [x] Implement alert rules engine (thresholds, persistence, cooldown) — **COMPLETED**
  - Standalone `dt.alerts` service with Kafka consumer, REST API, and in-memory registry
  - See docs/plans/alert_engine_implementation_plan.md for details
- [x] Migrate to unified PostgreSQL + TimescaleDB storage — **COMPLETED**
  - Replaced InfluxDB with TimescaleDB hypertables for measurements
  - Unified relational tables (sensors, plants, actuators, alerts, alert_events) in same database
  - Implemented continuous aggregates (1h rollups), retention (30d), and compression policies
  - See docs/plans/storage_architecture_implementation_plan.md for details
- [ ] Noise filtering (EWMA smoothing available; Kalman filter evaluation pending)
- [ ] Finalize calibration tables and normalization logic (Spark end-to-end pytest harness in place; wire remaining streaming stages)
- [ ] Create API endpoints `/logs`, `/actions`, `/configs`
- [ ] Create a Minimal UI for logs and alerts to expose to users
- [ ] Run QA: synthetic replays, dropouts, noisy to see how the system copes and compute DQ score metrics  

---

## 🧠 Changes Since Last Update
- Created Sensor validation config file (`dt/utils/preprocessing_config.yml`)
- Assigned imputation tuned to sampling rates:
  - DHT22 (2 min): window_average over 6 minutes (min 2 samples)
  - BH1750 (1 min): window_average over 3 minutes (min 3 samples)
  - Soil moisture (2 min): forward fill with decay; max gap 10 minutes
- Added smoothing strategy hook with pass-through default and EWMA option for post-imputation filters
- Introduced per-strategy imputation configs with new linear extrapolation option and typed loader
- Structured streaming job under `dt/data/preprocess/` now reads `dt.sensor.raw.*`, applies validators, imputation, smoothing, and publishes to `.proc` topics.
- Processed payloads include validation flags, data-quality scores, imputation markers, and optional `raw_value` for auditability.
- `SparkStateProvider` mediates tuple-backed `SensorState` so validation, imputation, and smoothing layers share consistent history windows.
- Added end-to-end calibration/normalization pytest harness validating profile lookups and processed payload fields.
- **2025-10-30**: Started pipeline refactoring (feature/pipeline-refactoring branch) to break monolithic pipeline.py (942 lines) into modular Chain of Responsibility architecture for better readability, testability, and extensibility.
- **2025-11-03**: Completed alert engine service (feature/alert-engine branch) with full TDD implementation:
  - Standalone `dt.alerts` package with config loader, rule evaluator, state registry, REST API, and Kafka consumer
  - YAML-based alert rules with threshold, range, DQ score, and validation flag conditions
  - Persistence counters and cooldown timers prevent alert fatigue
  - REST endpoints: POST /alerts/submit, POST /alerts/<id>/acknowledge, POST /alerts/<id>/clear, GET /alerts/active, GET /alert-rules
  - Publishes canonical AlertHistoryEvent messages (sensor/external variants) to `dt.alerts` topic for downstream consumption
  - 122 tests passing (including 5 end-to-end integration tests)
- **2025-11-08**: Completed storage architecture migration (feature/storage-architecture branch):
  - Migrated from InfluxDB to unified PostgreSQL + TimescaleDB storage
  - TimescaleDB hypertables for sensor measurements with automatic partitioning, compression, and 1h continuous aggregates
  - Relational tables for sensors, plants, actuators, alerts, and alert events (normalized schema)
  - Direct Flask-to-Storage architecture with SQLAlchemy Core for explicit query control
  - Implemented TimescaleStorage repository with full CRUD operations and testcontainers-based tests
  - Kafka bridge persists both measurements and alert events
  - SQL migrations via scripts/run_sql_migration.py with idempotent tracking

---

## ⚠️ Risks / Blockers
- **Spark load on Raspberry Pi** may exceed available RAM; considering external node for preprocessing.  
- **Sensor drift** (soil moisture) needs recalibration automation.  
- **Schema evolution** could break Kafka consumers if not versioned properly.  

---

## 🪄 Summary
Phase P1 (Data Preprocessing & Quality) is nearly complete:
- ✅ Validation and normalization of sensor data (Chain of Responsibility pipeline with calibration, validation, imputation, smoothing, normalization)
- ✅ Quality flagging, DQ scoring, and audit visibility (processed payloads include flags, dq_score, imputed markers, raw_value)
- ✅ Alert engine with rule-based evaluation, persistence counters, and REST API
- ✅ Unified PostgreSQL + TimescaleDB storage with hypertables, continuous aggregates, and relational tables
- 🔄 Calibration/normalization finalization (harness in place, streaming wiring pending)
- 🔄 Dashboard UI for alerts and logs (backend ready, frontend integration pending)

By end of P1 (Dec 2025), data pipelines will be fully validated and alert-ready, setting up for control automation (P2).  

---

## 🗃 Archived Contexts
*(None yet — first active context block created on Oct 2025)*
