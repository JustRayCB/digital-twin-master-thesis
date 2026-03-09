import json
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import Connection, text

from dt.communication.adapters import dump, load
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition, AlertHistoryEvent, ExternalAlertEvent, SensorAlertEvent)
from dt.communication.dataclasses.queries import (ActiveAlertsQuery,
                                                  AlertHistoryQuery)
from dt.data.database.base_storage import DatabaseStorage


class AlertStorage(DatabaseStorage, ABC):
    """Storage capability for alert definitions and history."""

    @abstractmethod
    def save_alert_definition(self, definition: AlertDefinition) -> None:
        """Upsert an alert definition.

        Parameters
        ----------
        definition : AlertDefinition
            The alert definition to save.
        """
        ...

    @abstractmethod
    def save_alert_event(self, event: AlertHistoryEvent) -> int:
        """Save an alert history event (and details) and return its ID.

        Parameters
        ----------
        event : AlertHistoryEvent
            The alert history event to store (including subclasses).

        Returns
        -------
        int
            The ID of the newly created alert history record.
        """
        ...

    @abstractmethod
    def get_alert_history(self, query: AlertHistoryQuery) -> list[AlertHistoryEvent]:
        """Retrieve alert history.

        Parameters
        ----------
        query : AlertHistoryQuery
            Query parameters (plant_id, limit).

        Returns
        -------
        list[AlertHistoryEvent]
            List of alert history events with full reconstruction from database context.
        """
        ...

    @abstractmethod
    def get_active_alerts(self, query: ActiveAlertsQuery) -> list[AlertHistoryEvent]:
        """Retrieve currently active alerts.

        Derives the current state of alerts by finding the latest history event
        for each alert definition and filtering for those that are not cleared.

        Parameters
        ----------
        query : ActiveAlertsQuery
            Query parameters (plant_id).

        Returns
        -------
        list[AlertHistoryEvent]
            List of the latest history event for each active alert.
        """
        ...


class ControllerStorage(DatabaseStorage, ABC):
    """Storage capability for controller state and action history."""

    @abstractmethod
    def get_mode(self, plant_id: int) -> ControlMode:
        """Get the current control mode for a plant.

        Parameters
        ----------
        plant_id : int
            The ID of the plant.

        Returns
        -------
        ControlMode
            The control mode configuration.
        """
        ...

    @abstractmethod
    def set_mode(self, mode: ControlMode) -> None:
        """Set the control mode for a plant.

        Parameters
        ----------
        mode : ControlMode
            Updated control mode configuration.
        """
        ...

    @abstractmethod
    def get_routines(self, plant_id: int) -> list[Routine]:
        """Get all routines for a plant.

        Parameters
        ----------
        plant_id : int
            The ID of the plant.

        Returns
        -------
        list[Routine]
            List of routines.
        """
        ...

    @abstractmethod
    def create_routine(self, routine: RoutineUpdate) -> int:
        """Create a new routine.

        Parameters
        ----------
        routine : RoutineUpdate
            The routine data including compiled rules.
        Returns
        -------
        int
            The ID of the newly created routine.
        """
        ...

    @abstractmethod
    def update_routine(self, routine_id: int, updates: RoutineUpdate) -> None:
        """Update a routine.

        Parameters
        ----------
        routine_id : int
            The ID of the routine to update.
        updates : RoutineUpdate
            The fields to update.
        """
        ...

    @abstractmethod
    def delete_routine(self, routine_id: int) -> None:
        """Delete a routine.

        Parameters
        ----------
        routine_id : int
            The ID of the routine to delete.
        """
        ...

    @abstractmethod
    def get_action_history(self, plant_id: int, limit: int = 50) -> list[ActionCommand]:
        """Get action execution history for a plant.

        Parameters
        ----------
        plant_id : int
            The ID of the plant.
        limit : int, optional
            Maximum number of records to return, by default 50.

        Returns
        -------
        list[ActionCommand]
            List of action execution records.
        """
        ...

    @abstractmethod
    def log_action_execution(self, action: ActionCommand) -> None:
        """Log an action execution (upsert).

        Parameters
        ----------
        action : ActionCommand
            The action command.
        """
        ...


class AlertsStore(AlertStorage):
    """Persistence for alert definitions and history."""

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

    def save_alert_event(self, event: AlertHistoryEvent) -> int:
        data = dump("db_row", event)

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
            event_id = self._insert_alert_history(conn, history_data)

            if isinstance(event, SensorAlertEvent) and detail_data:
                self._insert_sensor_alert_details(conn, event_id, detail_data)
            elif isinstance(event, ExternalAlertEvent) and detail_data:
                self._insert_external_alert_details(conn, event_id, detail_data)

            self.logger.info(f"Saved alert event {event_id} ({event.alert_key})")
            return event_id

    def get_alert_history(self, query: AlertHistoryQuery) -> list[AlertHistoryEvent]:
        with self._get_connection() as conn:
            history_rows = self._fetch_history_rows(conn, query)
            if not history_rows:
                return []

            ids = [row.id for row in history_rows]
            sensor_map = self._fetch_detail_map(conn, "alert_sensors", ids)
            external_map = self._fetch_detail_map(conn, "alert_external", ids)

            return [
                self._reconstruct_alert_event(row, sensor_map, external_map) for row in history_rows
            ]

    def get_active_alerts(self, query: ActiveAlertsQuery) -> list[AlertHistoryEvent]:
        with self._get_connection() as conn:
            sql = """
                SELECT DISTINCT ON (alert_key, plant_id)
                    id, alert_key, plant_id, timestamp, status, severity,
                    message, correlation_id, acknowledged_by, acknowledged_ts, cleared_ts
                FROM alert_history
                WHERE 1=1
            """
            params: dict[str, Any] = {}
            if query.plant_id is not None:
                sql += " AND plant_id = :plant_id"
                params["plant_id"] = query.plant_id

            sql += " ORDER BY alert_key, plant_id, timestamp DESC, id DESC"
            full_query = f"""
                WITH latest_events AS (
                    {sql}
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
        query = f"SELECT * FROM {table} WHERE alert_history_id = ANY(:ids)"
        rows = conn.execute(text(query), {"ids": ids}).fetchall()
        return {row.alert_history_id: row for row in rows}

    def _reconstruct_alert_event(
        self, row: Any, sensor_map: dict[int, Any], external_map: dict[int, Any]
    ) -> AlertHistoryEvent:
        event_id = row.id
        if event_id in sensor_map:
            return load("db_row", SensorAlertEvent, (row, sensor_map[event_id]))
        if event_id in external_map:
            return load("db_row", ExternalAlertEvent, (row, external_map[event_id]))
        return load("db_row", AlertHistoryEvent, row)
