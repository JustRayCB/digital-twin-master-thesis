# Working TODO (human view; source of truth = TodoWrite)
- [x] Implement storage architecture migration (PostgreSQL + TimescaleDB) — completed on feature/storage-architecture
- [ ] Wire alert service into dashboard for real-time alert display and acknowledgment UI
- [ ] Add dashboard configurability for TimescaleDB retention and aggregation policies
- [ ] Document migration path to managed PostgreSQL services (AWS RDS, Azure Database, etc.)
- [ ] Finalize calibration tables and normalization logic for greenhouse sensors (Spark end-to-end harness passing; wire catalog refresh + streaming updates)
- [ ] Model audit and action store schema (tables, migrations, retention)
- [ ] Evaluate Kalman smoothing strategy feasibility alongside EWMA
- [ ] Make the default strategy for Calibration/Normalization the Identity
(keep ≤10; archive to progress.md when done)
