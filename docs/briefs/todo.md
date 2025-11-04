# Working TODO (human view; source of truth = TodoWrite)
- [ ] Wire alert service into dashboard for real-time alert display and acknowledgment UI
- [ ] Add database persistence layer for alert history (extend audit/action store with alert table)
- [ ] Finalize calibration tables and normalization logic for greenhouse sensors (Spark end-to-end harness passing; wire catalog refresh + streaming updates)
- [ ] Model audit and action store schema (tables, migrations, retention)
- [ ] Evaluate Kalman smoothing strategy feasibility alongside EWMA
- [ ] Make the default strategy for Calibration/Normalization the Identity
(keep ≤10; archive to progress.md when done)
