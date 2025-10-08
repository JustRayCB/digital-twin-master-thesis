
# 🧭 Project Progress — *Preprocessing Module Branch*

Digital Twin for Plant Health Monitoring
Repository: `JustRayCB/digital-twin-master-thesis`
Branch: `preprocessing-module`
Date: **October 2025**

---

## ✅ **1. Completed Tasks**

### 1.1 System Foundation

* **Architecture operational**: Kafka → Preprocessing → InfluxDB → Flask Dashboard works end-to-end.
* **Modules online**:

  * `dt/data/database`: Stores sensor data and exposes REST API.
  * `dt/data/collector`: Reads sensors and publishes to Kafka.
  * `dt/communication`: Kafka producer/consumer utilities, DB clients and dataclasses for consistency.
  * `dt/webapp`: Displays real-time and historical readings.
  * `dt/data/preprocess`: New streaming module created for data cleaning (in progress).
* **Sensor drivers functional**: DHT22 (temp/humidity), BH1750 (light), soil moisture all read correctly.

---

### 1.2 Data Schema & Serialization

* **Dataclass schema defined** (`SensorData`): ensures every sensor message includes:

  * `timestamp`, `sensor_type`, `plant_id`, `value`, `units`, `correlation_id`.
* **Consistency guaranteed**: messages are JSON-serialized with uniform field naming.
* **Schema versioning ready**: allows adding new fields later (e.g. calibration info, DQ score, ...).

---


### 1.3 Kafka Streaming

* **Kafka topics created**:

  * `dt.sensors.<type>.raw` → for incoming data.
  * `dt.sensors.<type>.processed` → for validated data.
* **Data Collector publishes** to Kafka using `correlation_id`.
* **Database service consumes** and stores data into InfluxDB.
* **Preprocessing module prototype** consumes raw topics and applies cleaning logic (WIP).

---

### 1.4 Storage & API

* **InfluxDB connected and configured** for time-series storage.
* **Flask API routes operational**:

  * `/data/timestamp` – query data in a time range.
  * `/data/id` – get data for a given sensor.
  * `/bind_sensor` – register new sensors.
* **Dashboard live updates working** through Socket.IO.

---

### 1.5 Documentation & Setup

* **Poetry environment** cleaned and reproducible.
* **Makefile targets** added (`make db`, `make web`, `make main`).
* **Installation guide tested** on Raspberry Pi and desktop.
* **Roadmap alignment** verified with October 2025 milestones.

---

## 🔜 **2. Next Steps**

### 2.1 Finish Phase 1 (Preprocessing & Data Quality)

Goal: make the preprocessing service *production-ready* by **December 19, 2025**.

| Task                            | Description                                                                                  | Status         |
| ------------------------------- | -------------------------------------------------------------------------------------------- | -------------- |
| **Sensor Data Validation**     | Check ranges, RoC, stuck values and outliers; tag invalid data (DQ score).                  | 🔄 In progress |
| **Calibration & Normalization** | Build calibration tables (dry/saturated soil baselines, per-sensor normalization to [0–1]).  | ⏳ To do        |
| **Missing Data Handling**       | Implement forward-fill and interpolation for short gaps; flag longer outages.                | ⏳ To do        |
| **Alert Engine (v1)**           | Create rule-based system for threshold breaches with persistence window and cooldown.        | ⏳ To do        |
| **Audit & Action Store**        | Design SQLAlchemy models for `actions`, `alerts`, `configs`, `jobs`; add Alembic migrations. | ⏳ To do        |
| **Config Registry v0**          | Save and version user thresholds/schedules with rollback.                                    | ⏳ To do        |
| **REST API Extensions**         | Add `/alerts`, `/actions`, `/configs` endpoints and simple HTML tables in Flask.             | ⏳ To do        |
| **Testing & QA**                | Run synthetic data replays, chaos tests (dropouts/spikes), and compute Data Quality metrics. | ⏳ To do        |

---

### 2.2 Prepare for Phase 2 (Jan–Mar 2026) — Feedback Loop

* **Actuator Control**: GPIO drivers for pump, fan, light; separate power rails and safety fuses.
* **Control Logic**: rule-based watering (on when moisture < threshold, off after recovery).
* **Manual Override**: add dashboard buttons for human control.
* **Simulation Mode**: soil moisture bucket model for testing without hardware.
* **Safety Rules**: daily watering limits, E-stop, photoperiod enforcement.
  *(Target milestone: Mar 20, 2026)*

---

### 2.3 Prepare for Phase 3 (Mar–Jun 2026) — Analytics & ML

* **Feature Extraction**: compute rolling mean, slopes, diel variance, etc.
* **Forecast Model**: next-day soil moisture (linear regression or Prophet baseline).
* **Health Classifier**: 3-state (healthy / stressed / unhealthy) using rules → logistic regression.
* **Model Registry**: MLflow or custom versioned model manager.
* **Online Serving**: microservice scoring models on live data.
  *(Target milestone: Jun 12, 2026)*

---

## ⚠️ **3. Current Issues & Risks**

### 3.1 Hardware Reliability

* **DHT22 failures**: known instability; sometimes unreadable on Raspberry Pi.
* **Soil sensor drift**: readings vary over time — needs frequent recalibration.
* **Mitigation**: add redundancy or fallback averages between multiple sensors.

---

### 3.2 Spark Resource Limits

* **Spark Structured Streaming** is heavy for Raspberry Pi.
* Risk: high memory/CPU usage may cause latency or dropped messages.
* **Mitigation**: move Spark preprocessing to external machine, keep Pi for acquisition only.

---

### 3.3 Missing Data Channels

* **Topics not yet active**: `dt.alerts`, `dt.actions`, `dt.audit`.
* **Impact**: alerts and actions aren’t yet traceable end-to-end.
* **Fix**: complete implementation of the action/audit pipeline in next sprint.

---

### 3.4 Testing Gaps

* **Automated tests limited** to dataclass serialization.
* **No integration tests yet** for Kafka → Influx → Dashboard.
* **Plan**: add synthetic replay tests and continuous validation of data-quality metrics.

---

### 3.5 Performance & Latency

* Current target: **sensor-to-dashboard latency ≤ 2 s (p95)**.
* Need stress-tests with synthetic data to confirm performance and reliability.

---

## 📅 **Summary of Upcoming Milestones**

| Milestone | Target Date | Expected Outcome                             |
| --------- | ----------- | -------------------------------------------- |
| **M1**    | Oct 31 2025 | Validation gates and DQ dashboard live       |
| **M2**    | Dec 19 2025 | Preprocessing + alerting v1 production-ready |
| **M3**    | Feb 14 2026 | Actuator manual control implemented          |
| **M4**    | Mar 20 2026 | Closed-loop watering and lighting            |
| **M5**    | May 8 2026  | Forecast and classifier validated            |
| **M6**    | Jun 12 2026 | Full system integration complete             |

---

✅ *Current status:*
The system successfully collects and displays live data.
The preprocessing module is under development to achieve full data quality automation by December 2025.

