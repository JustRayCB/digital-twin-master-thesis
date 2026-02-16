"""HTTP client for the database service.

Provides a thin wrapper over the Flask database API for sensor/actuator metadata,
readings, alert history, and alert definition upserts.
"""

from __future__ import annotations

from typing import Any, Type

import requests

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
from dt.utils import Config, get_logger


class DatabaseApiClient:
    """Client for interacting with the database service HTTP API."""

    def __init__(self, base_url: str = Config.FLASK_DB_URL):
        self.base_url = base_url.rstrip("/")
        self.logger = get_logger(__name__)

    # ---------------------------------------------------------------------- #
    # Sensors / Actuators
    # ---------------------------------------------------------------------- #
    def bind_sensor(self, sensor: SensorDescriptor) -> int:
        """Register a sensor with the database."""
        try:
            response = requests.post(
                f"{self.base_url}/bind_sensor",
                json=dump("generic", sensor),
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
            return int(payload.get("sensor_id", -1))
        except requests.RequestException as exc:
            self.logger.error(f"Error binding sensor: {exc}")
            raise RuntimeError(f"Failed to bind sensor: {exc}") from exc

    def list_sensors(self) -> list[SensorDescriptor]:
        """Return all registered sensors."""
        try:
            response = requests.get(
                f"{self.base_url}/sensors",
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
            return [load("generic", SensorDescriptor, item) for item in payload]
        except requests.RequestException as exc:
            self.logger.error(f"Error listing sensors: {exc}")
            raise RuntimeError(f"Failed to list sensors: {exc}") from exc

    def list_actuators(self) -> list[dict[str, Any]]:
        """Return all registered actuators."""
        try:
            response = requests.get(
                f"{self.base_url}/actuators",
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            self.logger.error(f"Error listing actuators: {exc}")
            raise RuntimeError(f"Failed to list actuators: {exc}") from exc

    def bind_actuator(self, plant_id: int, name: str, relay_channel: int) -> int:
        """Register an actuator with the database."""
        payload = {"plant_id": plant_id, "name": name, "relay_channel": relay_channel}
        try:
            response = requests.post(
                f"{self.base_url}/bind_actuator",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
            body = response.json()
            return int(body.get("actuator_id", -1))
        except requests.RequestException as exc:
            self.logger.error(f"Error binding actuator: {exc}")
            raise RuntimeError(f"Failed to bind actuator: {exc}") from exc

    def list_plants(self) -> list[dict[str, Any]]:
        """Return all registered plants."""
        try:
            response = requests.get(
                f"{self.base_url}/plants",
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            self.logger.error(f"Error listing plants: {exc}")
            raise RuntimeError(f"Failed to list plants: {exc}") from exc

    def log_action_execution(self, action: ActionCommand) -> None:
        """Persist action execution status."""
        if action.status is None:
            raise ValueError("ActionCommand.status is required to log execution")
        payload = {"action": dump("generic", action)}
        try:
            response = requests.post(
                f"{self.base_url}/actions/log",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self.logger.error(f"Error logging action execution: {exc}")
            raise RuntimeError(f"Failed to log action execution: {exc}") from exc

    # ---------------------------------------------------------------------- #
    # Controller data
    # ---------------------------------------------------------------------- #
    def get_mode(self, plant_id: int) -> ControlMode:
        """Fetch controller mode for a plant."""
        try:
            response = requests.get(
                f"{self.base_url}/controller/mode",
                params={"plant_id": plant_id},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
            return load("generic", ControlMode, response.json())
        except requests.RequestException as exc:
            self.logger.error(f"Error fetching controller mode: {exc}")
            raise RuntimeError(f"Failed to fetch controller mode: {exc}") from exc

    def set_mode(self, mode: ControlMode) -> None:
        """Persist controller mode."""
        try:
            response = requests.put(
                f"{self.base_url}/controller/mode",
                json=dump("generic", mode),
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self.logger.error(f"Error setting controller mode: {exc}")
            raise RuntimeError(f"Failed to set controller mode: {exc}") from exc

    def get_routines(self, plant_id: int) -> list[Routine]:
        """Fetch routines for a plant."""
        try:
            response = requests.get(
                f"{self.base_url}/controller/routines",
                params={"plant_id": plant_id},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
            return [load("generic", Routine, item) for item in payload]
        except requests.RequestException as exc:
            self.logger.error(f"Error listing routines: {exc}")
            raise RuntimeError(f"Failed to list routines: {exc}") from exc

    def create_routine(self, routine: RoutineCreate, compiled: CompiledRoutineRules) -> int:
        """Create a new routine and return its ID."""
        payload = {
            "routine": dump("generic", routine),
            "compiled_json": dump("generic", compiled),
        }
        try:
            response = requests.post(
                f"{self.base_url}/controller/routines",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
            return int(response.json().get("id", -1))
        except requests.RequestException as exc:
            self.logger.error(f"Error creating routine: {exc}")
            raise RuntimeError(f"Failed to create routine: {exc}") from exc

    def update_routine(self, routine_id: int, updates: RoutineUpdate) -> None:
        """Update an existing routine."""
        try:
            response = requests.put(
                f"{self.base_url}/controller/routines/{routine_id}",
                json=dump("generic", updates),
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self.logger.error(f"Error updating routine: {exc}")
            raise RuntimeError(f"Failed to update routine: {exc}") from exc

    def delete_routine(self, routine_id: int) -> None:
        """Delete a routine."""
        try:
            response = requests.delete(
                f"{self.base_url}/controller/routines/{routine_id}",
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self.logger.error(f"Error deleting routine: {exc}")
            raise RuntimeError(f"Failed to delete routine: {exc}") from exc

    def get_action_history(self, plant_id: int, limit: int = 50) -> list[ActionCommand]:
        """Fetch action execution history."""
        try:
            response = requests.get(
                f"{self.base_url}/controller/actions/history",
                params={"plant_id": plant_id, "limit": limit},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
            return [load("generic", ActionCommand, item) for item in payload]
        except requests.RequestException as exc:
            self.logger.error(f"Error fetching action history: {exc}")
            raise RuntimeError(f"Failed to fetch action history: {exc}") from exc

    # ---------------------------------------------------------------------- #
    # Readings
    # ---------------------------------------------------------------------- #
    def query_readings(self, query: ReadingsQuery) -> list[ProcessedSensorData | AggregatedReading]:
        """Fetch processed readings or aggregates based on the query window."""
        params = dump("generic", query)
        try:
            response = requests.get(
                f"{self.base_url}/readings",
                params=params,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            self.logger.error(f"Error querying readings: {exc}")
            raise RuntimeError(f"Failed to query readings: {exc}") from exc

        target_cls: Type[ProcessedSensorData] | Type[AggregatedReading]
        target_cls = AggregatedReading if query.window == "1h" else ProcessedSensorData
        return [load("generic", target_cls, item) for item in payload]

    # ---------------------------------------------------------------------- #
    # Alerts
    # ---------------------------------------------------------------------- #
    def get_alert_history(self, query: AlertHistoryQuery) -> list[AlertHistoryEvent]:
        """Fetch alert history events (sensor or external)."""
        params = dump("generic", query)
        try:
            response = requests.get(
                f"{self.base_url}/alerts/history",
                params=params,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            self.logger.error(f"Error fetching alert history: {exc}")
            raise RuntimeError(f"Failed to fetch alert history: {exc}") from exc

        return [self._load_alert_event(item) for item in payload]

    def get_active_alerts(self, query: ActiveAlertsQuery) -> list[AlertHistoryEvent]:
        """Fetch currently active alerts from the database."""
        params = dump("generic", query)

        try:
            response = requests.get(
                f"{self.base_url}/alerts/active",
                params=params,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            self.logger.error(f"Error fetching active alerts: {exc}")
            raise RuntimeError(f"Failed to fetch active alerts: {exc}") from exc

        return [self._load_alert_event(item) for item in payload]

    def ensure_alert_definition(self, definition: AlertDefinition) -> None:
        """Persist an alert definition (idempotent upsert)."""
        payload = dump("generic", definition)
        try:
            response = requests.post(
                f"{self.base_url}/alerts/definitions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self.logger.error(f"Error upserting alert definition: {exc}")
            raise RuntimeError(f"Failed to upsert alert definition: {exc}") from exc

    # ---------------------------------------------------------------------- #
    # Internal helpers
    # ---------------------------------------------------------------------- #

    def _load_alert_event(self, item: dict[str, Any]) -> AlertHistoryEvent:
        """Load polymorphic alert event based on payload shape."""
        if "reading" in item:
            return load("generic", SensorAlertEvent, item)
        if "metadata" in item:
            return load("generic", ExternalAlertEvent, item)
        return load("generic", AlertHistoryEvent, item)
