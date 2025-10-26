from dataclasses import dataclass
from enum import StrEnum

from dt.communication.dataclasses.raw_sensor_data import RawSensorData


class ValidationFlag(StrEnum):
    """Enumeration of validation flags emitted by the preprocessing pipeline."""

    RANGE = "range_violation"
    RATE_OF_CHANGE = "rate_of_change_violation"
    STUCK = "stuck_violation"
    VALID = "valid_data_point"


@dataclass
class ProcessedSensorData(RawSensorData):
    """Represents a single processed data point from a sensor.

    This dataclass is used to store and transmit processed data read from sensors. It is
    sent via the messaging service to the web application and the database.

    NOTE: It is the same as RawSensorData but with additional fields for preprocessing results.

    Attributes
    ----------
    plant_id : int
        The ID of the plant associated with the sensor.
    sensor_id : int
        The ID of the sensor that generated the data.
    timestamp : float
        The Unix timestamp when the data was read.
    value : float
        The value read from the sensor.
    unit : str
        The unit of measurement for the sensor's value (e.g., "Celsius").
    topic : Topics
        The Kafka topic to which this data belongs.
    correlation_id : str
        A unique ID for tracing this data point through the system.
    flags : Dict[ValidationFlag, bool]
        A dictionary of flags indicating the results of various data quality checks.
    dq_score : float
        A score representing the overall data quality after processing.
    imputed : bool
        A boolean indicating whether the value was imputed during processing.
    raw_value : float, optional
        Original sensor reading when imputation or smoothing altered the output value.
    """

    flags: dict[ValidationFlag, bool]
    dq_score: float
    imputed: bool
    raw_value: float | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        self.flags = {
            (flag if isinstance(flag, ValidationFlag) else ValidationFlag(flag)): bool(value)
            for flag, value in dict(self.flags).items()
        }
        self.dq_score = float(self.dq_score)
        self.imputed = bool(self.imputed)
        if self.raw_value is not None:
            self.raw_value = float(self.raw_value)

    @staticmethod
    def get_spark_schema():
        """Convert the dataclass to a PySpark StructType schema.

        This method generates a PySpark StructType schema that corresponds
        to the fields of the ProcessedSensorData dataclass. This is useful for
        creating Spark DataFrames from processed sensor data.

        Returns
        -------
        StructType
            A PySpark StructType schema representing the dataclass fields.
        """
        # Importing here to avoid needed dependency if Spark is not used
        from pyspark.sql.types import (BooleanType, DoubleType, MapType,
                                       StringType, StructField, StructType)

        raw_sensor_schema = RawSensorData.get_spark_schema()
        processed_sensor_schema = StructType(
            raw_sensor_schema.fields
            + [
                StructField("flags", MapType(StringType(), BooleanType()), nullable=False),
                StructField("dq_score", DoubleType(), nullable=False),
                StructField("imputed", BooleanType(), nullable=False),
                StructField("raw_value", DoubleType(), nullable=True),
            ]
        )
        return processed_sensor_schema

    @classmethod
    def from_row(cls, row):
        """Create a processed sensor data instance from a Spark Row."""
        base = RawSensorData.from_row(row)
        return cls(
            plant_id=base.plant_id,
            sensor_id=base.sensor_id,
            timestamp=base.timestamp,
            value=base.value,
            unit=base.unit,
            topic=base.topic,
            correlation_id=base.correlation_id,
            flags=getattr(row, "flags"),
            dq_score=getattr(row, "dq_score"),
            imputed=getattr(row, "imputed"),
            raw_value=getattr(row, "raw_value", None),
        )
