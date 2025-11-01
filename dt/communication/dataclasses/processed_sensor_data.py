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
    calibrated_value : float, optional
        Sensor reading after calibration but before imputation or smoothing.
    normalized_value : float, optional
        Calibrated reading scaled into the normalization range.
    calibration_profile_id : str, optional
        Identifier of the calibration profile applied when producing the reading.
    normalization_profile_id : str, optional
        Identifier of the normalization profile used for scaling.
    """

    flags: dict[ValidationFlag, bool]
    dq_score: float
    imputed: bool
    raw_value: float | None = None
    calibrated_value: float | None = None
    normalized_value: float | None = None
    calibration_profile_id: str | None = None
    normalization_profile_id: str | None = None

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
        if self.calibrated_value is not None:
            self.calibrated_value = float(self.calibrated_value)
        if self.normalized_value is not None:
            self.normalized_value = float(self.normalized_value)
        if self.calibration_profile_id is not None:
            self.calibration_profile_id = str(self.calibration_profile_id)
        if self.normalization_profile_id is not None:
            self.normalization_profile_id = str(self.normalization_profile_id)

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
                StructField("calibrated_value", DoubleType(), nullable=True),
                StructField("normalized_value", DoubleType(), nullable=True),
                StructField("calibration_profile_id", StringType(), nullable=True),
                StructField("normalization_profile_id", StringType(), nullable=True),
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
            calibrated_value=getattr(row, "calibrated_value", None),
            normalized_value=getattr(row, "normalized_value", None),
            calibration_profile_id=getattr(row, "calibration_profile_id", None),
            normalization_profile_id=getattr(row, "normalization_profile_id", None),
        )

    @classmethod
    def from_raw_sensor_data(
        cls,
        raw_data: RawSensorData,
        proc_value: float,
        flags: dict[ValidationFlag, bool],
        dq_score: float,
        imputed: bool,
        calibrated_value: float | None = None,
        normalized_value: float | None = None,
        calibration_profile_id: str | None = None,
        normalization_profile_id: str | None = None,
    ) -> "ProcessedSensorData":
        """Create a ProcessedSensorData instance from a RawSensorData instance.

        Parameters
        ----------
        raw_data : RawSensorData
            The raw sensor data instance to base the processed data on.
        proc_value : float
            The processed value to be stored in the processed data.
        flags : Dict[ValidationFlag, bool]
            A dictionary of flags indicating the results of various data quality checks.
        dq_score : float
            A score representing the overall data quality after processing.
        imputed : bool
            A boolean indicating whether the value was imputed during processing.

        Returns
        -------
        ProcessedSensorData
            A new instance of ProcessedSensorData with the provided attributes.
        """
        return ProcessedSensorData(
            plant_id=raw_data.plant_id,
            sensor_id=raw_data.sensor_id,
            timestamp=raw_data.timestamp,
            value=proc_value,
            unit=raw_data.unit,
            topic=raw_data.topic,
            correlation_id=raw_data.correlation_id,
            flags=flags,
            dq_score=dq_score,
            imputed=imputed,
            raw_value=raw_data.value,
            calibrated_value=calibrated_value,
            normalized_value=normalized_value,
            calibration_profile_id=calibration_profile_id,
            normalization_profile_id=normalization_profile_id,
        )
