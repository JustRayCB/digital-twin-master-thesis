from __future__ import annotations

from dataclasses import dataclass, field

from dt.communication.dataclasses.raw_sensor_data import RawSensorData


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

    def to_dict(self) -> dict[str, float]:
        """Serialise the record into a dictionary for storage.

        Returns
        -------
        dict[str, float]
            Dictionary representation of the FlatlineRecord.
        """
        return {"value": float(self.value), "timestamp": float(self.timestamp)}

    def to_tuple(self) -> tuple[float, float]:
        """Serialise the record into a tuple matching the Spark schema."""
        return (float(self.value), float(self.timestamp))

    @classmethod
    def from_tuple(cls, values: tuple[float, float] | None) -> FlatlineRecord | None:
        """Hydrate a record from a tuple payload."""
        if not values:
            return None
        value, timestamp = values
        return cls(value=float(value), timestamp=float(timestamp))


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
        last_valid = self.last_valid.to_tuple() if self.last_valid else None
        flatline = self.flatline.to_tuple() if self.flatline else None
        history = [entry.to_tuple() for entry in self.history]
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

        last_valid = RawSensorData.from_tuple(last_valid_payload) if last_valid_payload else None
        flatline = FlatlineRecord.from_tuple(flatline_payload)
        history = [
            RawSensorData.from_tuple(item) for item in history_payload or [] if item is not None
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
