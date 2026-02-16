import json
from contextlib import contextmanager
from typing import Any, Generator, Optional

from sqlalchemy import Connection, Engine, create_engine, text
from typing_extensions import override

from dt.communication.adapters import dump, load
from dt.communication.dataclasses import AggregatedReading, ProcessedSensorData, SensorDescriptor
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertHistoryEvent,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.dataclasses.controller import (
    ActionCommand,
    CompiledRoutineRules,
    ControlMode,
    Routine,
    RoutineCreate,
    RoutineUpdate,
)
from dt.communication.dataclasses.queries import ActiveAlertsQuery, AlertHistoryQuery, ReadingsQuery
from dt.data.database.storage import Storage
from dt.utils import Config, get_logger


class TimescaleStorage(Storage):
    """PostgreSQL + TimescaleDB implementation of the Storage interface.

    Provides unified storage for time-series readings in TimescaleDB hypertables
    and relational metadata/alerts in PostgreSQL tables.
    """

    def __init__(
        self,
        engine: Optional[Engine] = None,
        database_url: Optional[str] = None,
        pool_size: Optional[int] = None,
    ) -> None:
        self.logger = get_logger(__name__)
        if engine:
            self.engine = engine
            self.logger.info("Using provided SQLAlchemy engine")
        else:
            url = database_url or Config.PG_DATABASE_URL
            pool = int(pool_size or Config.SQL_POOL_SIZE)
            self.engine = create_engine(url, pool_size=pool, pool_pre_ping=True)
            self.logger.info(f"Created SQLAlchemy engine with pool size {pool}")

    # =========================================================================
    # Core / Connection
    # =========================================================================

    @contextmanager
    def _get_connection(self) -> Generator[Connection, None, None]:
        """Provide a transactional database connection."""
        conn = self.engine.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _get_id(self, result: Any) -> int:
        """Extract newly created ID from a RETURNING clause result."""
        new_id = result.scalar()
        if new_id is None or not str(new_id).isdigit():
            raise RuntimeError("Failed to retrieve ID from database operation")
        return int(new_id)

    @override
    def create_table(self) -> None:
        self.logger.info("Schema initialization handled by SQL migrations")

    @override
    def close(self) -> None:
        if self.engine:
            self.engine.dispose()
            self.logger.info("TimescaleStorage engine disposed")

    # =========================================================================
    # Controller Data
    # =========================================================================

    @override
    def get_mode(self, plant_id: int) -> ControlMode:
        query = "SELECT * FROM controller_modes WHERE plant_id = :plant_id"
        with self._get_connection() as conn:
            result = conn.execute(text(query), {"plant_id": plant_id}).fetchone()
            if result:
                return load("db_row", ControlMode, result)
            # Default mode if not found
            return ControlMode(plant_id, False, "routine")

    @override
    def set_mode(self, mode: ControlMode) -> None:
        query = """
            INSERT INTO controller_modes (plant_id, ai_autopilot_enabled, owner, updated_at)
            VALUES (:plant_id, :ai_autopilot_enabled, :owner, COALESCE(:updated_at, NOW()))
            ON CONFLICT (plant_id) DO UPDATE
            SET ai_autopilot_enabled = EXCLUDED.ai_autopilot_enabled,
                owner = EXCLUDED.owner,
                updated_at = EXCLUDED.updated_at
        """
        with self._get_connection() as conn:
            conn.execute(text(query), dump("db_row", mode))

    @override
    def get_routines(self, plant_id: int) -> list[Routine]:
        query = "SELECT * FROM routines WHERE plant_id = :plant_id ORDER BY id"
        with self._get_connection() as conn:
            result = conn.execute(text(query), {"plant_id": plant_id}).fetchall()
            return [load("db_row", Routine, row) for row in result]

    @override
    def create_routine(self, routine: RoutineCreate, compiled: CompiledRoutineRules) -> int:
        query = """
            INSERT INTO routines (plant_id, name, enabled, graph_json, compiled_json)
            VALUES (:plant_id, :name, :enabled, :graph_json, :compiled_json)
            RETURNING id
        """
        params = dump("db_row", routine)
        params["compiled_json"] = json.dumps(dump("generic", compiled))
        with self._get_connection() as conn:
            new_id = self._get_id(conn.execute(text(query), params))
            self.logger.info(f"Created routine {new_id} for plant {routine.plant_id}")
            return new_id

    @override
    def update_routine(self, routine_id: int, updates: RoutineUpdate) -> None:
        fields = []
        params = {"id": routine_id}
        updates_data = dump("db_row", updates)
        allowed_fields = {"plant_id", "name", "enabled", "graph_json", "compiled_json"}
        for key, value in updates_data.items():
            if value is None:
                continue
            if key in allowed_fields:
                fields.append(f"{key} = :{key}")
                params[key] = value

        if not fields:
            return

        query = f"UPDATE routines SET {', '.join(fields)}, updated_at = NOW() WHERE id = :id"
        with self._get_connection() as conn:
            conn.execute(text(query), params)
            self.logger.info(f"Updated routine {routine_id}")

    @override
    def delete_routine(self, routine_id: int) -> None:
        query = "DELETE FROM routines WHERE id = :id"
        with self._get_connection() as conn:
            conn.execute(text(query), {"id": routine_id})
            self.logger.info(f"Deleted routine {routine_id}")

    @override
    def get_action_history(self, plant_id: int, limit: int = 50) -> list[ActionCommand]:
        query = """
            SELECT * FROM action_executions
            WHERE plant_id = :plant_id
            ORDER BY started_at DESC
            LIMIT :limit
        """
        with self._get_connection() as conn:
            result = conn.execute(text(query), {"plant_id": plant_id, "limit": limit}).fetchall()
            return [load("db_row", ActionCommand, row) for row in result]

    @override
    def log_action_execution(self, action: ActionCommand) -> None:
        query = """
            INSERT INTO action_executions (
                action_id, plant_id, actuator_id, routine_id, source, command, duration,
                reason, status, error_message, correlation_id, started_at
            ) VALUES (
                :action_id, :plant_id, :actuator_id, :routine_id, :source, :command, :duration,
                :reason, :status, :error_message, :correlation_id, to_timestamp(:started_at)
            )
            ON CONFLICT (action_id, started_at) DO UPDATE
            SET status = EXCLUDED.status,
                error_message = EXCLUDED.error_message,
                ended_at = CASE
                    WHEN EXCLUDED.status IN ('completed', 'failed', 'rejected') THEN NOW()
                    ELSE action_executions.ended_at
                END
        """
        if action.status is None:
            raise ValueError("ActionCommand.status is required to log execution")
        with self._get_connection() as conn:
            conn.execute(text(query), dump("db_row", action))

    # =========================================================================
    # Plants, Sensors, Actuators - Non-time-series data
    # =========================================================================

    @override
    def upsert_plant(
        self,
        plant_id: int | None = None,
        name: str = "",
        notes: str | None = None,
    ) -> int:
        query = (
            "UPDATE plants SET name = :name, notes = :notes WHERE id = :id"
            if plant_id
            else "INSERT INTO plants (name, notes) VALUES (:name, :notes) RETURNING id"
        )
        params = {"name": name, "notes": notes, "id": plant_id}

        with self._get_connection() as conn:
            if plant_id:
                conn.execute(text(query), params)
                self.logger.info(f"Updated plant {plant_id}")
                return plant_id
            else:
                new_id = self._get_id(conn.execute(text(query), params))
                self.logger.info(f"Created plant {new_id}")
                return new_id

    @override
    def list_plants(self) -> list[dict[str, Any]]:
        query = "SELECT id, name, notes FROM plants ORDER BY id"
        with self._get_connection() as conn:
            result = conn.execute(text(query))
            plants = [{"id": r[0], "name": r[1], "notes": r[2]} for r in result]
            self.logger.info(f"Retrieved {len(plants)} plants")
            return plants

    @override
    def register_sensor(self, sensor: SensorDescriptor) -> int:
        query = """
            INSERT INTO sensors (plant_id, name, pin, read_interval, status)
            VALUES (:plant_id, :name, :pin, :read_interval, :status)
            ON CONFLICT (plant_id, name) DO UPDATE
            SET pin = EXCLUDED.pin,
                read_interval = EXCLUDED.read_interval,
                status = EXCLUDED.status
            RETURNING id
        """
        with self._get_connection() as conn:
            sensor_id = self._get_id(conn.execute(text(query), dump("db_row", sensor)))
            self.logger.info(f"Registered sensor {sensor.name} (ID: {sensor_id})")
            return sensor_id

    @override
    def list_sensors(self) -> list[SensorDescriptor]:
        query = "SELECT id, plant_id, name, pin, read_interval, status FROM sensors ORDER BY id"
        with self._get_connection() as conn:
            sensors = [load("db_row", SensorDescriptor, row) for row in conn.execute(text(query))]
            self.logger.info(f"Retrieved {len(sensors)} sensors")
            return sensors

    @override
    def register_actuator(self, plant_id: int, name: str, relay_channel: int) -> int:
        query = """
            INSERT INTO actuators (plant_id, name, relay_channel, status)
            VALUES (:plant_id, :name, :relay_channel, :status)
            ON CONFLICT (plant_id, name) DO UPDATE
            SET relay_channel = EXCLUDED.relay_channel,
                status = EXCLUDED.status
            RETURNING id
        """
        params = {
            "plant_id": plant_id,
            "name": name,
            "relay_channel": relay_channel,
            "status": "active",
        }
        with self._get_connection() as conn:
            act_id = self._get_id(conn.execute(text(query), params))
            self.logger.info(f"Registered actuator {name} (ID: {act_id})")
            return act_id

    @override
    def list_actuators(self) -> list[dict[str, Any]]:
        query = "SELECT id, plant_id, name, relay_channel, status FROM actuators ORDER BY id"
        with self._get_connection() as conn:
            actuators = [row._asdict() for row in conn.execute(text(query))]
            self.logger.info(f"Retrieved {len(actuators)} actuators")
            return actuators

    # =========================================================================
    # Readings (Time-series)
    # =========================================================================

    @override
    def ingest_reading(self, data: ProcessedSensorData) -> None:
        query = """
            INSERT INTO sensor_readings (
                timestamp, sensor_id, plant_id, topic, value, unit,
                correlation_id, dq_score, imputed, flags,
                raw_value, calibrated_value, normalized_value,
                calibration_profile_id, normalization_profile_id
            ) VALUES (
                to_timestamp(:timestamp), :sensor_id, :plant_id, :topic,
                :value, :unit, :correlation_id, :dq_score, :imputed,
                :flags, :raw_value, :calibrated_value,
                :normalized_value, :calibration_profile_id,
                :normalization_profile_id
            )
        """
        with self._get_connection() as conn:
            conn.execute(text(query), dump("db_row", data))
            self.logger.info(f"Ingested reading for sensor {data.sensor_id} at {data.timestamp}")

    @override
    def query_readings(self, query_data: ReadingsQuery) -> list[ProcessedSensorData]:
        base_query = """
            SELECT timestamp, sensor_id, plant_id, topic, value, unit,
                   correlation_id, dq_score, imputed, flags,
                   raw_value, calibrated_value, normalized_value,
                   calibration_profile_id, normalization_profile_id
            FROM sensor_readings
            WHERE 1=1
        """
        query, params = self._build_filter_query(base_query, query_data, time_col="timestamp")
        with self._get_connection() as conn:
            result = conn.execute(text(query), params)
            readings = [load("db_row", ProcessedSensorData, row) for row in result]
            self.logger.info(f"Retrieved {len(readings)} readings")
            return readings

    @override
    def query_aggregates(self, query_data: ReadingsQuery) -> list[AggregatedReading]:
        window = query_data.window
        if window != "1h":
            raise ValueError(f"Unsupported window: {window}. Currently only '1h' is supported.")

        base_query = f"""
            SELECT bucket, sensor_id, plant_id, topic, unit,
                   avg_value, min_value, max_value, sample_count,
                   avg_dq_score, imputed_count
            FROM sensor_readings_{window}
            WHERE 1=1
        """
        query, params = self._build_filter_query(base_query, query_data, time_col="bucket")
        with self._get_connection() as conn:
            result = conn.execute(text(query), params)
            readings = [load("db_row", AggregatedReading, row) for row in result]
            self.logger.info(f"Retrieved {len(readings)} {window}-aggregated readings")
            return readings

    def _build_filter_query(
        self,
        base_query: str,
        query_data: ReadingsQuery,
        time_col: str,
    ) -> tuple[str, dict[str, Any]]:
        """Helper to append common WHERE clauses for time-series queries."""
        params: dict[str, Any] = {}
        query = base_query

        if query_data.sensor_id is not None:
            query += "\nAND sensor_id = :sensor_id"
            params["sensor_id"] = query_data.sensor_id
        if query_data.plant_id is not None:
            query += "\nAND plant_id = :plant_id"
            params["plant_id"] = query_data.plant_id
        if query_data.topic is not None:
            query += "\nAND topic = :topic"
            params["topic"] = query_data.topic
        if query_data.since is not None:
            query += f"\nAND {time_col} >= to_timestamp(:since)"
            params["since"] = query_data.since
        if query_data.until is not None:
            query += f"\nAND {time_col} <= to_timestamp(:until)"
            params["until"] = query_data.until

        query += f"\nORDER BY {time_col} ASC"
        return query, params

    # =========================================================================
    # Alerts (Definitions & History)
    # =========================================================================

    @override
    def save_alert_definition(self, definition: AlertDefinition) -> None:
        query = """
            INSERT INTO alert_definitions (
                alert_key, plant_id, sensor_id, source,
                rule_id, rule_name, kind,
                persistence_count, cooldown_seconds
            ) VALUES (
                :alert_key, :plant_id, :sensor_id, :source,
                :rule_id, :rule_name, :kind,
                :persistence_count, :cooldown_seconds
            )
            ON CONFLICT (alert_key, plant_id) DO UPDATE SET
                sensor_id = EXCLUDED.sensor_id,
                source = EXCLUDED.source,
                rule_id = EXCLUDED.rule_id,
                rule_name = EXCLUDED.rule_name,
                kind = EXCLUDED.kind,
                persistence_count = EXCLUDED.persistence_count,
                cooldown_seconds = EXCLUDED.cooldown_seconds
        """
        with self._get_connection() as conn:
            conn.execute(text(query), dump("db_row", definition))
            self.logger.info(
                f"Saved alert definition {definition.alert_key} for plant {definition.plant_id}"
            )

    @override
    def save_alert_event(self, event: AlertHistoryEvent) -> int:
        """Persist an alert event and its type-specific details."""
        data = dump("db_row", event)

        # Handle different structure returned by adapters
        # Generic AlertHistoryEvent -> dict
        # SensorAlertEvent -> {'history': dict, 'sensor': dict}
        # ExternalAlertEvent -> {'history': dict, 'external': dict}
        if isinstance(event, SensorAlertEvent):
            history_data, detail_data = data["history"], data["sensor"]
        elif isinstance(event, ExternalAlertEvent):
            history_data, detail_data = data["history"], data["external"]
        else:
            history_data, detail_data = data, None
            self.logger.warning(
                f"Saving generic AlertHistoryEvent without details: {event.alert_key}."
                f"This may indicate a missing implementation."
            )

        alert_key = history_data["alert_key"]
        plant_id = history_data["plant_id"]

        with self._get_connection() as conn:
            self._assert_alert_definition_exists(conn, alert_key, plant_id)

            # 1. Insert Base History
            event_id = self._insert_alert_history(conn, history_data)

            # 2. Insert Details (if applicable)
            if isinstance(event, SensorAlertEvent) and detail_data:
                self._insert_sensor_alert_details(conn, event_id, detail_data)
            elif isinstance(event, ExternalAlertEvent) and detail_data:
                self._insert_external_alert_details(conn, event_id, detail_data)

            self.logger.info(f"Saved alert event {event_id} ({event.alert_key})")
            return event_id

    def _assert_alert_definition_exists(
        self, conn: Connection, alert_key: str, plant_id: int
    ) -> None:
        query = """
            SELECT 1 FROM alert_definitions
            WHERE alert_key = :alert_key AND plant_id = :plant_id
            LIMIT 1
        """
        exists = conn.execute(
            text(query), {"alert_key": alert_key, "plant_id": plant_id}
        ).scalar_one_or_none()
        if exists is None:
            raise ValueError(
                f"Missing alert definition for key '{alert_key}' and plant {plant_id}. "
                "Call save_alert_definition before saving alert events."
            )

    def _insert_alert_history(self, conn: Connection, data: dict[str, Any]) -> int:
        query = """
            INSERT INTO alert_history (
                alert_key, plant_id, timestamp, status, severity,
                message, correlation_id,
                acknowledged_by, acknowledged_ts, cleared_ts
            ) VALUES (
                :alert_key, :plant_id, to_timestamp(:timestamp), :status, :severity,
                :message, :correlation_id,
                :acknowledged_by, to_timestamp(:acknowledged_ts), to_timestamp(:cleared_ts)
            ) RETURNING id
        """
        return self._get_id(conn.execute(text(query), data))

    def _insert_sensor_alert_details(
        self, conn: Connection, event_id: int, data: dict[str, Any]
    ) -> None:
        data["alert_history_id"] = event_id
        query = """
            INSERT INTO alert_sensors (
                alert_history_id, sensor_id, plant_id, timestamp,
                value, unit, topic, correlation_id,
                flags, dq_score, imputed,
                raw_value, calibrated_value, normalized_value,
                calibration_profile_id, normalization_profile_id,
                threshold_op, threshold_value, range_min, range_max
            ) VALUES (
                :alert_history_id, :sensor_id, :plant_id, to_timestamp(:timestamp),
                :value, :unit, :topic, :correlation_id,
                :flags, :dq_score, :imputed,
                :raw_value, :calibrated_value, :normalized_value,
                :calibration_profile_id, :normalization_profile_id,
                :threshold_op, :threshold_value, :range_min, :range_max
            )
        """
        conn.execute(text(query), data)

    def _insert_external_alert_details(
        self, conn: Connection, event_id: int, data: dict[str, Any]
    ) -> None:
        data["alert_history_id"] = event_id
        # Ensure metadata is JSON string for JSONB column
        if isinstance(data.get("metadata"), dict):
            data["metadata"] = json.dumps(data["metadata"])

        query = """
            INSERT INTO alert_external (
                alert_history_id, plant_id, metadata
            ) VALUES (
                :alert_history_id, :plant_id, :metadata
            )
        """
        conn.execute(text(query), data)

    @override
    def get_alert_history(self, query: AlertHistoryQuery) -> list[AlertHistoryEvent]:
        """Fetch and reconstruct alert history with all details."""
        with self._get_connection() as conn:
            # 1. Fetch Base Rows
            history_rows = self._fetch_history_rows(conn, query)
            if not history_rows:
                return []

            # 2. Fetch Related Details (Bulk)
            ids = [row.id for row in history_rows]
            sensor_map = self._fetch_detail_map(conn, "alert_sensors", ids)
            external_map = self._fetch_detail_map(conn, "alert_external", ids)

            # 3. Reconstruct Objects
            return [
                self._reconstruct_alert_event(row, sensor_map, external_map) for row in history_rows
            ]

    @override
    def get_active_alerts(self, query_data: ActiveAlertsQuery) -> list[AlertHistoryEvent]:
        """Retrieve currently active alerts."""
        with self._get_connection() as conn:
            # 1. Find latest event for each alert_key (per plant)
            # Using DISTINCT ON to get the latest event per alert_key and plant_id
            query = """
                SELECT DISTINCT ON (alert_key, plant_id)
                    id, alert_key, plant_id, timestamp, status, severity,
                    message, correlation_id, acknowledged_by, acknowledged_ts, cleared_ts
                FROM alert_history
                WHERE 1=1
            """
            params: dict[str, Any] = {}
            if query_data.plant_id is not None:
                query += " AND plant_id = :plant_id"
                params["plant_id"] = query_data.plant_id

            query += " ORDER BY alert_key, plant_id, timestamp DESC, id DESC"

            # Filter by active status
            full_query = f"""
                WITH latest_events AS (
                    {query}
                )
                SELECT * FROM latest_events
                WHERE status != 'cleared'
                ORDER BY timestamp DESC
            """

            rows = conn.execute(text(full_query), params).fetchall()
            if not rows:
                return []

            ids = [row.id for row in rows]
            sensor_map = self._fetch_detail_map(conn, "alert_sensors", ids)
            external_map = self._fetch_detail_map(conn, "alert_external", ids)

            alerts = [self._reconstruct_alert_event(row, sensor_map, external_map) for row in rows]
            self.logger.info(f"Retrieved {len(alerts)} active alerts")
            return alerts

    def _fetch_history_rows(self, conn: Connection, query_data: AlertHistoryQuery) -> list[Any]:
        query = """
            SELECT id, alert_key, plant_id, timestamp, status, severity,
                   message, correlation_id, acknowledged_by, acknowledged_ts, cleared_ts
            FROM alert_history
            WHERE 1=1
        """
        params: dict[str, Any] = {"limit": query_data.limit}
        if query_data.plant_id is not None:
            query += " AND plant_id = :plant_id"
            params["plant_id"] = query_data.plant_id
        query += " ORDER BY timestamp DESC LIMIT :limit"

        return list(conn.execute(text(query), params).fetchall())

    def _fetch_detail_map(self, conn: Connection, table: str, ids: list[int]) -> dict[int, Any]:
        """Fetch details from a related table and map them by alert_history_id."""
        query = f"SELECT * FROM {table} WHERE alert_history_id = ANY(:ids)"
        rows = conn.execute(text(query), {"ids": ids}).fetchall()
        return {row.alert_history_id: row for row in rows}

    def _reconstruct_alert_event(
        self, row: Any, sensor_map: dict[int, Any], external_map: dict[int, Any]
    ) -> AlertHistoryEvent:
        """Map DB rows to the appropriate AlertHistoryEvent subclass."""
        event_id = row.id
        if event_id in sensor_map:
            return load("db_row", SensorAlertEvent, (row, sensor_map[event_id]))
        elif event_id in external_map:
            return load("db_row", ExternalAlertEvent, (row, external_map[event_id]))
        else:
            return load("db_row", AlertHistoryEvent, row)
