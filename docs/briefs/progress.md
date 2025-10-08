# Progress — Week of <YYYY-MM-DD>
## ✅ Done
- <bullet w/ PR links>
## 🔜 Next
- <bullet w/ acceptance checkboxes>
## ⚠️ Issues / Decisions Needed
- <bullet, who/when>

# Progress — Week of 2025-10-08
**Branch:** preprocessing-module  
**Phase:** P1 (Preprocessing & Data Quality)

---

## ✅ Done
- Architecture operational end-to-end (Kafka → Preprocessing → InfluxDB → Flask).  
- Sensor drivers functional: DHT22, BH1750, soil moisture.  
- Dataclass schema (`SensorData`) finalized and versioning ready.  
- Storage in InfluxDB and accessible via Flask with API endpoints `/data/timestamp`, `data/id`, ...
- Kafka topics (`dt.sensors.*`) live and tested.  
- Flask dashboard streaming confirmed.  
- Docs & Setup: Poetry environment cleaned, Make targets added, Pi install tested.  

---

## 🔜 Next

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
System runs live end-to-end; preprocessing under construction.  
Target: production-quality validation and alerting by **Dec 19, 2025**.
