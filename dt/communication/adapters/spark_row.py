"""Spark Row adapter for PySpark DataFrame conversions.

Handles conversions for Spark streaming and batch processing:
- Topics enum ↔ full topic name (enum.value)
- dict[ValidationFlag, bool] ↔ dict[str, bool] (Spark doesn't support enum keys)
"""

from typing import Any, TypeVar

from typing_extensions import override

from dt.communication.adapters.base import SerializationAdapter
from dt.communication.dataclasses.processed_sensor_data import ProcessedSensorData, ValidationFlag
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics

T = TypeVar("T")


class SparkRowAdapter(SerializationAdapter):
    """Adapter for converting objects to/from Spark Row format.

    Supports:
    - RawSensorData
    - ProcessedSensorData (with flags conversion)
    """

    @override
    def dump(self, obj: Any) -> Any:
        """Serialize ProcessedSensorData to Spark Row.

        Conversions:
        - topic: Topics enum → full topic name (.value)
        - flags: dict[ValidationFlag, bool] → dict[str, bool]

        Parameters
        ----------
        obj : ProcessedSensorData
            Object to serialize.

        Returns
        -------
        pyspark.sql.Row
            Spark Row object.
        """
        # Convert to dict
        from dataclasses import asdict

        from pyspark.sql import Row

        data = asdict(obj)

        # Handle specific dataclasses for topic and flags conversion
        if isinstance(obj, ProcessedSensorData):
            # Convert topic enum to full topic name
            data["topic"] = obj.topic.value

            # Convert flags enum keys to string keys
            data["flags"] = {flag.value: value for flag, value in obj.flags.items()}
        elif isinstance(obj, RawSensorData):
            data["topic"] = obj.topic.value

        return Row(**data)

    @override
    def load(self, cls: type[T], row: Any) -> T:
        """Deserialize Spark Row to object.

        Handles:
        - RawSensorData
        - ProcessedSensorData (converts flags string keys to enum)

        Parameters
        ----------
        cls : type[T]
            Target class (RawSensorData or ProcessedSensorData).
        row : pyspark.sql.Row
            Spark Row object.

        Returns
        -------
        T
            Deserialized object instance.
        """
        # Prioritize more specific classes first
        if cls == ProcessedSensorData:
            return self._load_processed_sensor_data(row)  # type: ignore
        elif cls == RawSensorData:
            return self._load_raw_sensor_data(row)  # type: ignore
        else:
            raise TypeError(f"SparkRowAdapter does not support loading {cls.__name__}")

    def _load_raw_sensor_data(self, row: Any) -> RawSensorData:
        """Load RawSensorData from Spark Row.

        Parameters
        ----------
        row : pyspark.sql.Row
            Spark Row with RawSensorData fields.

        Returns
        -------
        RawSensorData
            Deserialized object.
        """
        row_dict = self._row_to_dict(row)
        row_dict["topic"] = Topics(row_dict["topic"])
        row_dict.pop("event_time", None)  # Remove watermark
        return RawSensorData(**row_dict)

    def _load_processed_sensor_data(self, row: Any) -> ProcessedSensorData:
        """Load ProcessedSensorData from Spark Row.

        Parameters
        ----------
        row : pyspark.sql.Row
            Spark Row with ProcessedSensorData fields.

        Returns
        -------
        ProcessedSensorData
            Deserialized object.
        """
        row_dict = self._row_to_dict(row)

        row_dict["topic"] = Topics(row_dict["topic"])

        # Convert flags string keys back to enum keys
        flags = {
            ValidationFlag(flag_name): bool(value) for flag_name, value in row_dict["flags"].items()
        }
        row_dict["flags"] = flags
        return ProcessedSensorData(**row_dict)

    def _row_to_dict(self, row: Any) -> dict[str, Any]:
        """Convert Spark Row or named tuple to dict.

        This helper handles two different contexts:
        1. Driver context: Data collected via .collect() returns pyspark.sql.Row (asDict).
        2. Worker context: Vectorized APIs (applyInPandas) pass pandas namedtuples (_asdict).
        """
        if hasattr(row, "asDict"):
            # Driver context: Actual Spark Row objects
            return row.asDict()
        elif hasattr(row, "_asdict"):
            # Worker context: Pandas namedtuples from vectorized execution
            return row._asdict()
        raise TypeError(f"Cannot convert {type(row)} to dict. Expected Spark Row or namedtuple.")
