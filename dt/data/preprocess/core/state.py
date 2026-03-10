from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable

from pyspark.sql.streaming.state import GroupState

from dt.communication.adapters import dump, load
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.utils.config import Config


@dataclass
class FlatlineRecord:
    """Captured metadata describing flatline detection for a sensor.

    Parameters
    ----------
    value : float
        Representative sensor value observed during the flatline.
    timestamp : float
        Epoch timestamp (seconds) recorded at the start of the flatline.
    """

    value: float
    timestamp: float

    @staticmethod
    def get_spark_schema():
        """Return a Spark schema compatible with FlatlineRecord storage.

        Returns
        -------
        StructType
            Spark schema describing the FlatlineRecord structure.
        """
        from pyspark.sql.types import DoubleType, StructField, StructType

        return StructType(
            [
                StructField("value", DoubleType(), nullable=False),
                StructField("timestamp", DoubleType(), nullable=False),
            ]
        )


@dataclass
class SensorState:
    """Internal representation of persisted sensor state.

    Parameters
    ----------
    last_valid : RawSensorData, optional
        Most recent reading accepted by the pipeline.
    flatline : FlatlineRecord, optional
        Metadata describing the latest flatline detection event.
    history : list[RawSensorData], optional
        Chronological list of recent valid readings.
    """

    last_valid: RawSensorData | None = None
    flatline: FlatlineRecord | None = None
    history: list[RawSensorData] = field(default_factory=list)

    def update(self, reading: RawSensorData, max_history_length: int) -> None:
        """Update internal state based on a newly accepted reading.

        Parameters
        ----------
        reading : RawSensorData
            Newly accepted reading to track.
        max_history_length : int
            Maximum number of entries to retain in history.
        """
        self.last_valid = reading
        # Fresh data implies the sensor is no longer considered stuck.
        self.flatline = None

        self.append_history(reading, max_history_length)

    def record_flatline(self, value: float, timestamp: float) -> None:
        """Store flatline detection metadata.

        Parameters
        ----------
        value : float
            Observed value during the flatline interval.
        timestamp : float
            Timestamp associated with the flatline detection.
        """
        self.flatline = FlatlineRecord(value=value, timestamp=timestamp)

    def to_payload(self) -> tuple[object, object, list[tuple]]:
        """Serialise the state into a tuple for storage.

        Returns
        -------
        tuple
            Tuple compatible with Spark state storage semantics.
        """
        last_valid = dump("tuple", self.last_valid) if self.last_valid else None
        flatline = dump("tuple", self.flatline) if self.flatline else None
        history = [dump("tuple", entry) for entry in self.history]
        return (last_valid, flatline, history)

    @classmethod
    def from_payload(cls, payload: tuple | None) -> "SensorState":
        """Hydrate state from a previously persisted payload.

        Parameters
        ----------
        payload : tuple or None
            Tuple produced by :meth:`to_payload`.

        Returns
        -------
        SensorState
            Deserialised state object populated from the payload.
        """
        if not payload:
            return cls()
        if not isinstance(payload, tuple):
            raise TypeError("SensorState payload must be a tuple.")

        last_valid_payload = payload[0] if len(payload) > 0 else None
        flatline_payload = payload[1] if len(payload) > 1 else None
        history_payload = payload[2] if len(payload) > 2 else []

        last_valid = (
            load("tuple", RawSensorData, last_valid_payload) if last_valid_payload else None
        )
        flatline = load("tuple", FlatlineRecord, flatline_payload) if flatline_payload else None
        history = [
            load("tuple", RawSensorData, item) for item in history_payload or [] if item is not None
        ]
        return cls(last_valid=last_valid, flatline=flatline, history=history)

    def append_history(self, reading: RawSensorData, max_length: int) -> None:
        """Append a reading to the rolling history while enforcing a max size.

        Parameters
        ----------
        reading : RawSensorData
            Newly accepted reading to track.
        max_length : int
            Maximum number of entries to retain in history.
        """
        self.history.append(reading)
        overflow = len(self.history) - max_length
        if overflow > 0:
            del self.history[:overflow]

    def recent_history(
        self, window_seconds: float, reference_timestamp: float
    ) -> list[RawSensorData]:
        """Return history entries within the specified time window.

        Parameters
        ----------
        window_seconds : float
            Width of the desired time window in seconds.
        reference_timestamp : float
            Upper bound timestamp used when trimming history.

        Returns
        -------
        list[RawSensorData]
            Sequence of readings restricted to the requested window.
        """
        if window_seconds <= 0:
            self.history.clear()
            return []
        cutoff = reference_timestamp - window_seconds
        trimmed = [
            entry
            for entry in self.history
            if cutoff <= float(entry.timestamp) <= float(reference_timestamp)
        ]
        self.history = trimmed
        return trimmed

    @staticmethod
    def get_spark_schema():
        """Return a Spark schema compatible with SensorState storage.

        Returns
        -------
        StructType
            Spark schema describing the SensorState structure.
        """
        from pyspark.sql.types import ArrayType, StructField, StructType

        return StructType(
            [
                StructField("last_valid", RawSensorData.get_spark_schema(), nullable=True),
                StructField("flatline", FlatlineRecord.get_spark_schema(), nullable=True),
                StructField(
                    "history",
                    ArrayType(RawSensorData.get_spark_schema()),
                    nullable=True,
                ),
            ]
        )


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


class SparkStateProvider(StateProvider):
    """State adapter backed by Spark Structured Streaming GroupState."""

    def __init__(
        self,
        group_state: GroupState,
        max_history_length: int = int(Config.MAX_STATE_HISTORY_LENGTH),
    ) -> None:
        """Initialise the provider with an existing Spark GroupState object.

        Parameters
        ----------
        group_state : pyspark.sql.streaming.state.GroupState
            Stateful context provided by Spark while processing a sensor stream.
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
