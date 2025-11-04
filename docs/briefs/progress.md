# Progress — Week of <YYYY-MM-DD>
## ✅ Done
- <bullet w/ PR links>
## 🔜 Next
- <bullet w/ acceptance checkboxes>
## ⚠️ Issues / Decisions Needed
- <bullet, who/when>

# Progress — Week of 2025-11-03
**Branch:** feature/alert-engine
**Phase:** P1 (Preprocessing & Data Quality)

---

## ✅ Done

### Alert Engine Service Implementation

**Date**: 2025-11-03
**Branch**: feature/alert-engine

Implemented a standalone alert engine service providing centralized alert management with
rule-based evaluation, state tracking, and REST API for programmatic integration.

**Changes:**
- Created `dt/alerts/` package with modular architecture:
  - `config/`: YAML rule loader with validation (alert_rule.py, manager.py)
  - `state/`: In-memory registry with persistence counters, cooldown timers, and acknowledgments (registry.py, models.py)
  - `engine/`: Rule evaluator supporting 4 condition types, and Kafka publisher (evaluator.py, publisher.py)
  - `service.py`: Kafka consumer subscribing to all processed sensor topics
  - `api.py`: Flask REST API with 5 endpoints (submit, acknowledge, clear, list active, list rules)
  - `app.py`: Application factory with dependency injection
- Implemented TDD throughout with 122 tests passing (8 test files):
  - Unit tests for config loader, evaluator, registry, publisher, API
  - Integration tests for service consumer behavior
  - End-to-end tests validating full alert lifecycle
- Alert rules configured via `dt/utils/alert_rules.yml` with 6 example rules
- Supports threshold, range, DQ score, and validation flag conditions
- Persistence mechanism prevents alerts until N consecutive violations occur
- Cooldown timers prevent alert fatigue by suppressing repeated alerts
- REST API enables external submissions from AI/control modules
- Publishes canonical `AlertEvent` messages to `dt.alerts` Kafka topic
- In-memory state maintains alert history, acknowledgments, and timestamps

**Benefits:**
- Centralized alert authority prevents duplicate/conflicting alerts
- Configurable persistence and cooldown prevent alert fatigue
- REST API enables integration with AI, control, and UI modules
- Kafka publishing provides audit trail and downstream consumption
- Full test coverage ensures reliability

**Test coverage**: 122 tests across all components

---

## 🔜 Next

| Task                            | Description                                                                                  | Status         |
| ------------------------------- | -------------------------------------------------------------------------------------------- | -------------- |
| **Audit & Action Store**        | Design SQLAlchemy models for `actions`, `alerts`, `configs`, `jobs`; add Alembic migrations. | ⏳ To do        |
| **Config Registry v0**          | Save and version user thresholds/schedules with rollback.                                    | ⏳ To do        |
| **REST API Extensions**         | Add `/logs`, `/actions`, `/configs` endpoints and simple HTML tables in Flask.             | ⏳ To do        |
| **Alert UI Integration**        | Wire alert service into dashboard for real-time alert display and acknowledgment.            | ⏳ To do        |

---

## ⚠️ Issues / Risks
- Alert state is in-memory only; service restart clears active alerts (document limitation, add persistence layer in future)
- No database persistence yet for alert history (planned for audit store phase)

---

# Progress — Week of 2025-10-28
**Branch:** feature/pipeline-refactoring
**Phase:** P1 (Preprocessing & Data Quality)

---

## ✅ Done

### Preprocessing Pipeline Refactoring

**Date**: 2025-10-31
**Branch**: feature/pipeline-refactoring

Refactored the monolithic `pipeline.py` (942 lines) into a modular, extensible
architecture using Chain of Responsibility pattern.

**Changes:**
- Created `dt/data/preprocess/pipeline/` package with modular components
- Implemented five processor classes (Calibration, Validation, Imputation, Smoothing, Normalization)
- Added `ConfigurationManager` for centralized config and strategy management
- Added `ProcessingPipeline` chain executor
- Added `PipelineBuilder` factory for pipeline construction
- Created `SparkStreamingAdapter` to isolate Spark concerns
- Updated `main.py` to use new modular pipeline
- Added comprehensive unit tests for all components
- Added end-to-end integration test
- Removed legacy monolithic pipeline implementation

**Benefits:**
- Better readability: Clear separation of concerns
- Better testability: Components tested independently without Spark
- Better extensibility: Easy to add new processing steps
- Better maintainability: No global state, encapsulated caching

**Test coverage**: A lot of new pipeline package

---

## 🔜 Next

| Task                            | Description                                                                                  | Status         |
| ------------------------------- | -------------------------------------------------------------------------------------------- | -------------- |
| **Alert Engine (v1)**           | Create rule-based system for threshold breaches with persistence window and cooldown.        | ⏳ To do        |
| **Audit & Action Store**        | Design SQLAlchemy models for `actions`, `alerts`, `configs`, `jobs`; add Alembic migrations. | ⏳ To do        |
| **Config Registry v0**          | Save and version user thresholds/schedules with rollback.                                    | ⏳ To do        |
| **REST API Extensions**         | Add `/alerts`, `/actions`, `/configs` endpoints and simple HTML tables in Flask.             | ⏳ To do        |

---

## ⚠️ Issues / Risks
- None flagged this week

---

# Progress — Week of 2025-10-08
**Branch:** preprocessing-module  
**Phase:** P1 (Preprocessing & Data Quality)

---

## ✅ Done
- Preprocessing validators for range, rate-of-change, and stuck detection covered by deterministic Spark tests.
- Data-quality scoring, imputation strategies (forward fill, window averaging, linear extrapolation guardrails), and smoothing hook integrated into the streaming pipeline.
- Structured streaming job publishes processed payloads with Kafka sink wiring and topic remapping utilities.
- Architecture operational end-to-end (Kafka → Preprocessing → InfluxDB → Flask).  
- Sensor drivers functional: DHT22, BH1750, soil moisture.  
- Dataclass schema (`SensorData`) finalized and versioning ready.  
- Storage in InfluxDB and accessible via Flask with API endpoints `/data/timestamp`, `data/id`, ...
- Kafka topics (`dt.sensors.*`) live and tested.  
- Flask dashboard streaming confirmed.  
- Docs & Setup: Poetry environment cleaned, Make targets added, Pi install tested.  
- Spark end-to-end calibration/normalization pytest harness verifies catalog defaults and overrides.

---

## 🔜 Next

| Task                            | Description                                                                                  | Status         |
| ------------------------------- | -------------------------------------------------------------------------------------------- | -------------- |
| **Sensor Data Validation**     | Check ranges, RoC, stuck values and outliers; tag invalid data (DQ score).                  | ✅ Done         |
| **Calibration & Normalization** | Build calibration tables (dry/saturated soil baselines, per-sensor normalization to [0–1]).  | ⏳ To do        |
| **Missing Data Handling**       | Implement forward-fill and interpolation for short gaps; flag longer outages.                | ✅ Done         |
| **Alert Engine (v1)**           | Create rule-based system for threshold breaches with persistence window and cooldown.        | ⏳ To do        |
| **Audit & Action Store**        | Design SQLAlchemy models for `actions`, `alerts`, `configs`, `jobs`; add Alembic migrations. | ⏳ To do        |
| **Config Registry v0**          | Save and version user thresholds/schedules with rollback.                                    | ⏳ To do        |
| **REST API Extensions**         | Add `/alerts`, `/actions`, `/configs` endpoints and simple HTML tables in Flask.             | ⏳ To do        |
| **Testing & QA**                | Run synthetic data replays, chaos tests (dropouts/spikes), and compute Data Quality metrics. | ⏳ To do        |


---

## ⚠️ Issues / Risks
- **DHT22 instability** — occasional read failures.  
- **Spark load** — may exceed Pi limits; offload option considered.  
- **Incomplete topics** — alerts/actions/audit not yet connected.  
- **Testing coverage** — integration tests missing for Kafka → Influx → Dashboard.  

---

## 📅 Upcoming Milestones

| Milestone | Target Date | Expected Outcome                             |
| --------- | ----------- | -------------------------------------------- |
| **M1**    | Oct 31 2025 | Validation gates and DQ dashboard live       |
| **M2**    | Dec 19 2025 | Preprocessing + alerting v1 production-ready |
| **M3**    | Feb 14 2026 | Actuator manual control implemented          |
| **M4**    | Mar 20 2026 | Closed-loop watering and lighting            |
| **M5**    | May 8 2026  | Forecast and classifier validated            |
| **M6**    | Jun 12 2026 | Full system integration complete             |

---

## 🧾 Summary
System runs live end-to-end; preprocessing streaming job validating, imputing, and publishing processed payloads through Kafka.  
Target: production-quality validation and alerting by **Dec 19, 2025**.
