from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.state import FlatlineRecord


class StateProvider(ABC):
    """Interface describing state management for preprocessing validators."""

    def __init__(self, max_history_length: int) -> None:
        """Initialise the state provider.

        Parameters
        ----------
        max_history_length : int
            Maximum number of historical readings to retain for each sensor.
        """
        self.max_history_length = max_history_length

    @abstractmethod
    def get_last_valid(self, sensor_id: int) -> RawSensorData | None:
        """Return the most recent accepted reading for the given sensor.

        Parameters
        ----------
        sensor_id : int
            Identifier for the sensor stream.

        Returns
        -------
        RawSensorData or None
            Latest accepted reading, or ``None`` when none exists.
        """

    @abstractmethod
    def update(self, sensor_id: int, reading: RawSensorData) -> None:
        """Persist the latest accepted reading for downstream checks.

        Parameters
        ----------
        sensor_id : int
            Identifier for the sensor stream.
        reading : RawSensorData
            Reading to mark as accepted.
        """

    @abstractmethod
    def record_flatline(self, sensor_id: int, value: float, timestamp: float) -> None:
        """Store stuck detection metadata to inform imputation.

        Parameters
        ----------
        sensor_id : int
            Identifier for the sensor stream.
        value : float
            Observed value during the flatline interval.
        timestamp : float
            Timestamp associated with the flatline detection.
        """

    @abstractmethod
    def get_flatline(self, sensor_id: int) -> FlatlineRecord | None:
        """Retrieve previously recorded flatline metadata if present.

        Parameters
        ----------
        sensor_id : int
            Identifier for the sensor stream.

        Returns
        -------
        FlatlineRecord or None
            Stored flatline metadata if available.
        """

    @abstractmethod
    def get_recent_history(
        self, sensor_id: int, window_seconds: float, reference_timestamp: float
    ) -> Iterable[RawSensorData]:
        """Return valid readings for the sensor within the requested window.

        Parameters
        ----------
        sensor_id : int
            Identifier for the sensor stream.
        window_seconds : float
            Width of the rolling window to examine.
        reference_timestamp : float
            Upper bound timestamp for the window.

        Returns
        -------
        Iterable[RawSensorData]
            Sequence of readings contained in the requested window.
        """
