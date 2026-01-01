"""HTTP client for the database service.

Provides a thin wrapper over the Flask database API for sensor/actuator metadata,
readings, alert history, and alert definition upserts.
"""

from __future__ import annotations

from typing import Any, Iterable, Type

import requests

from dt.communication.adapters import dump, load
from dt.communication.dataclasses import AggregatedReading, ProcessedSensorData, SensorDescriptor
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertHistoryEvent,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.dataclasses.queries import (
    ActiveAlertsQuery,
    AlertHistoryQuery,
    ReadingsQuery,
)
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
