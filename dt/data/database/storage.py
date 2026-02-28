from abc import ABC, abstractmethod
from typing import Any

from dt.communication.dataclasses import (
    AggregatedReading,
    ProcessedSensorData,
    SensorDescriptor,
)
from dt.communication.dataclasses.controller import ActionCommand
from dt.communication.dataclasses.controller import ControlMode, Routine, RoutineUpdate
from dt.communication.dataclasses.queries import (
    ActiveAlertsQuery,
    AlertHistoryQuery,
    ReadingsQuery,
)
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertHistoryEvent,
)


class Storage(ABC):
    """Abstract base class for storage implementations"""

    @abstractmethod
    def create_table(self) -> None:
        """Initialize storage schema"""
        pass

    @abstractmethod
    def upsert_plant(
        self, plant_id: int | None = None, name: str = "", notes: str | None = None
    ) -> int:
        """Create or update a plant record.

        Parameters
        ----------
        plant_id : int, optional
            If provided, updates the existing plant. Otherwise, creates a new plant.
        name : str
            The name of the plant.
        notes : str, optional
            Additional notes about the plant.

        Returns
        -------
        int
            The ID of the created or updated plant.
        """
        pass

    @abstractmethod
    def list_plants(self) -> list[dict[str, Any]]:
        """List all plants.

        Returns
        -------
        list[dict[str, Any]]
            List of plant records as dictionaries.
        """
        pass

    @abstractmethod
    def register_sensor(self, sensor: SensorDescriptor) -> int:
        """Register a new sensor and return its assigned ID.

        Parameters
        ----------
        sensor : SensorDescriptor
            The sensor descriptor to register.

        Returns
        -------
        int
            The assigned ID of the newly registered sensor.
        """
        pass

    @abstractmethod
    def list_sensors(self) -> list[SensorDescriptor]:
        """Return all registered sensors.

        Returns
        -------
        list[SensorDescriptor]
            List of all registered sensor descriptors.
        """
        pass

    @abstractmethod
    def register_actuator(self, plant_id: int, name: str, pin: int, relay_channel: int) -> int:
        """Register a new actuator and return its assigned ID.

        Parameters
        ----------
        plant_id : int
            The ID of the plant this actuator belongs to.
        name : str
            The name of the actuator.
        pin : int
            The GPIO pin the actuator is connected to.
        relay_channel : int
            The relay channel this actuator is connected to.

        Returns
        -------
        int
            The assigned ID of the newly registered actuator.
        """
        pass

    @abstractmethod
    def list_actuators(self) -> list[dict[str, Any]]:
        """List all actuators.

        Returns
        -------
        list[dict[str, Any]]
            List of actuator records as dictionaries.
        """
        pass

    @abstractmethod
    def ingest_reading(self, data: ProcessedSensorData) -> None:
        """Ingest a processed sensor reading into the hypertable.

        Parameters
        ----------
        data : ProcessedSensorData
            The processed sensor data to ingest.
        """
        pass

    def ingest_readings(self, datas: list[ProcessedSensorData]) -> None:
        """Ingest multiple processed sensor readings into the hypertable.

        Parameters
        ----------
        datas : list[ProcessedSensorData]
            The list of processed sensor data to ingest.
        """
        for data in datas:
            self.ingest_reading(data)

    @abstractmethod
    def query_readings(self, query: ReadingsQuery) -> list[ProcessedSensorData]:
        """Query raw readings from the hypertable.

        Parameters
        ----------
        query : ReadingsQuery
            The query parameters (sensor_id, plant_id, topic, time range, etc.).

        Returns
        -------
        list[ProcessedSensorData]
            List of raw sensor reading objects ordered by time ascending.
        """
        pass

    @abstractmethod
    def query_aggregates(self, query: ReadingsQuery) -> list[AggregatedReading]:
        """Query aggregated readings from continuous aggregates.

        Parameters
        ----------
        query : ReadingsQuery
            The query parameters including aggregation window.

        Returns
        -------
        list[AggregatedReading]
            List of aggregated reading objects ordered by bucket time.
        """
        pass

    @abstractmethod
    def save_alert_definition(self, definition: AlertDefinition) -> None:
        """Upsert an alert definition.

        Parameters
        ----------
        definition : AlertDefinition
            The alert definition to save.
        """
        pass

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
        pass

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
        pass

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
        pass

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
        pass

    @abstractmethod
    def set_mode(self, mode: ControlMode) -> None:
        """Set the control mode for a plant.

        Parameters
        ----------
        mode : ControlMode
            Updated control mode configuration.
        """
        pass

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
        pass

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
        pass

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
        pass

    @abstractmethod
    def delete_routine(self, routine_id: int) -> None:
        """Delete a routine.

        Parameters
        ----------
        routine_id : int
            The ID of the routine to delete.
        """
        pass

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
        pass

    @abstractmethod
    def log_action_execution(self, action: ActionCommand) -> None:
        """Log an action execution (upsert).

        Parameters
        ----------
        action : ActionCommand
            The action command.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close any open connections"""
        pass
