from __future__ import annotations

from pyspark.sql.streaming.state import GroupState

from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.state import FlatlineRecord, SensorState
from dt.utils.config import Config

from .state import StateProvider


class SparkStateProvider(StateProvider):
    """State adapter backed by Spark Structured Streaming GroupState."""

    def __init__(
        self,
        group_state: GroupState,
        sensor_id: int,
        max_history_length: int = int(Config.MAX_STATE_HISTORY_LENGTH),
    ) -> None:
        """Initialise the provider with an existing Spark GroupState object.

        Parameters
        ----------
        group_state : pyspark.sql.streaming.state.GroupState
            Stateful context provided by Spark while processing a sensor group.
        sensor_id : int
            Sensor identifier used for logging and debugging (unused in logic).
        max_history_length : int
            Maximum number of historical readings to retain for each sensor,
            by default int(Config.MAX_STATE_HISTORY_LENGTH)
        """
        super().__init__(max_history_length=max_history_length)
        self._group_state: GroupState = group_state
        payload: tuple | None = None
        if group_state.exists:
            retrieved_raw = group_state.get
            if retrieved_raw is not None and not isinstance(retrieved_raw, tuple):
                raise TypeError("SparkStateProvider expected state payload to be a tuple.")
            payload = retrieved_raw
        self._state: SensorState = SensorState.from_payload(payload)

    def _sync(self) -> None:
        """Synchronise in-memory state with the underlying Spark state store."""
        self._group_state.update(self._state.to_payload())

    def get_last_valid(self, sensor_id: int) -> RawSensorData | None:
        """Return the most recent accepted reading for ``sensor_id``.

        Parameters
        ----------
        sensor_id : int
            Identifier for the sensor stream.

        Returns
        -------
        RawSensorData or None
            Latest accepted reading, or ``None`` when none exists.
        """
        return self._state.last_valid

    def update(self, sensor_id: int, reading: RawSensorData) -> None:
        """Persist the latest accepted reading for downstream checks.

        Parameters
        ----------
        sensor_id : int
            Identifier for the sensor stream.
        reading : RawSensorData
            Reading to mark as accepted.
        """
        self._state.update(reading, self.max_history_length)
        self._sync()

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
        self._state.record_flatline(value=float(value), timestamp=float(timestamp))
        self._sync()

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
        return self._state.flatline

    def get_recent_history(
        self, sensor_id: int, window_seconds: float, reference_timestamp: float
    ) -> list[RawSensorData]:
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
        list[RawSensorData]
            Sequence of readings contained in the requested window.
        """
        history = self._state.recent_history(
            window_seconds=window_seconds,
            reference_timestamp=reference_timestamp,
        )
        self._sync()
        return history
