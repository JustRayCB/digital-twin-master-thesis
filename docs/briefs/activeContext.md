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
**Branch:** preprocessing-module  
**Phase:** P1 — Data Preprocessing & Quality  
**Window:** Oct–Dec 2025  

---

## 🎯 Focus & Exit Criteria
**Focus:** Build a production-ready real-time preprocessing pipeline ensuring sensor data validity, integrity, and readiness for analytics.  
**Exit criteria (target Dec 2025):**
- Data validation gates (range, rate, stuck, flatline) ≥ 99% pass rate
- DQ score and alerting active in dashboard
- Schema versioning and audit log stable
- Influx retention & rollups automated
- Basic alerting rules engine functional
- Action logging schema and API endpoints defined

---

## 🧩 Near-Term Tasks (This Sprint)
- [x] Define and implement sensor event schema
- [ ] Sensor data validation pipelines/rules (range, RoC, stuck or flatline, DQ scoring)
- [ ] Implement missing data handling (FFILL + capped interpolation) when readings are missing or dropped
- [ ] Noise filtering, integrate EWMA smoothing and optional Kalman filter  
- [ ] Finalize calibration tables and normalization logic  
- [ ] Rollups and retention policy for InfluxDB
- [ ] Setup of a non-TS database (Postgres) for audit logs and alert/action tracking
- [ ] Implement alert rules engine (thresholds, persistence, cooldown)  
- [ ] Finalize action/audit log schemas and migrations  
- [ ] Create API endpoints `/logs`, `/alerts`, `/actions`, `/configs`  
- [ ] Create a Minimal UI for logs and alerts to expose to users
- [ ] Run QA: synthetic replays, dropouts, noisy to see how the system copes and compute DQ score metrics  

---

## 🧠 Changes Since Last Update
- Created Sensor validation config file (`dt/utils/preprocessing_config.yml`)

---

## ⚠️ Risks / Blockers
- **Spark load on Raspberry Pi** may exceed available RAM; considering external node for preprocessing.  
- **Sensor drift** (soil moisture) needs recalibration automation.  
- **Schema evolution** could break Kafka consumers if not versioned properly.  

---

## 🪄 Summary
The preprocessing-module branch now focuses on:
- Validation and normalization of sensor data  
- Quality flagging, DQ scoring, and audit visibility  
- Preparing alerting and action logging foundations  

By end of P1 (Dec 2025), data pipelines should be fully validated and alert-ready, setting up for control automation (P2).  

---

## 🗃 Archived Contexts
*(None yet — first active context block created on Oct 2025)*
