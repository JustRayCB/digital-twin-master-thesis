from dataclasses import dataclass


from dt.communication.dataclasses.serializable import JsonSerializable
from dt.communication.topics import Topics


@dataclass
class RawSensorData(JsonSerializable):
    """Represents a single raw data point from a sensor.

    This dataclass is used to store and transmit raw data read from sensors. It is
    sent via the messaging service to the web application and the database.

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
    """

    plant_id: int
    sensor_id: int
    timestamp: float
    value: float
    unit: str
    topic: Topics
    correlation_id: str

    def __post_init__(self):
        self.plant_id = int(self.plant_id)
        self.sensor_id = int(self.sensor_id)
        self.timestamp = float(self.timestamp)
        self.value = float(self.value)
        self.unit = str(self.unit)
        self.topic = Topics(self.topic)
        self.correlation_id = str(self.correlation_id)

    def shrink_data(self):
        """Return a simplified dictionary for client-side use.

        This method returns a dictionary containing only the sensor value and
        timestamp, which is useful for sending data through SocketIO to the
        web dashboard.

        Returns
        -------
        dict
            A dictionary with "value" and "time" keys.
        """
        return {"value": self.value, "time": self.timestamp}

    @property
    def data_type(self):
        """Return the short name of the data type from the topic.

        Returns
        -------
        str
            The short name of the data type (e.g., "temperature").
        """
        return self.topic.short_name

    def py_to_js_timestamp(self):
        """Convert the timestamp from Python (seconds) to JavaScript (ms).

        This method modifies the `timestamp` attribute in-place, multiplying it
        by 1000 to convert it from seconds to milliseconds. This is necessary
        for compatibility with JavaScript clients, which expect timestamps in
        milliseconds since the epoch.
        """
        self.timestamp = self.timestamp * 1000

    @staticmethod
    def get_spark_schema():
        """Convert the dataclass to a PySpark StructType schema.

        This method generates a PySpark StructType schema that corresponds
        to the fields of the RawSensorData dataclass. This is useful for
        creating Spark DataFrames from raw sensor data.

        Returns
        -------
        StructType
            A PySpark StructType schema representing the dataclass fields.
        """
        # Importing here to avoid needed dependency if Spark is not used
        from pyspark.sql.types import (DoubleType, IntegerType, StringType,
                                       StructField, StructType)

        return StructType(
            [
                StructField("plant_id", IntegerType(), nullable=False),
                StructField("sensor_id", IntegerType(), nullable=False),
                StructField("timestamp", DoubleType(), nullable=False),
                StructField("value", DoubleType(), nullable=False),
                StructField("unit", StringType(), nullable=False),
                StructField("topic", StringType(), nullable=False),
                StructField("correlation_id", StringType(), nullable=False),
            ]
        )

    def to_tuple(self):
        """Convert the RawSensorData instance to a tuple for Spark storage.

        This method converts the attributes of the RawSensorData instance
        into a tuple format that is compatible with Spark DataFrame storage.

        Returns
        -------
        tuple
            A tuple containing the attributes of the RawSensorData instance.
        """
        return (
            self.plant_id,
            self.sensor_id,
            self.timestamp,
            self.value,
            self.unit,
            self.topic.value,
            self.correlation_id,
        )

    @classmethod
    def from_tuple(cls, values: tuple):
        """Create a RawSensorData instance from a tuple.

        This class method constructs a RawSensorData instance using data
        provided in a tuple format. It maps the elements of the tuple to
        the corresponding attributes of the dataclass.

        Parameters
        ----------
        values : tuple
            A tuple containing the raw sensor data.

        Returns
        -------
        RawSensorData
            An instance of RawSensorData populated with data from the tuple.
        """
        if values is None:
            raise TypeError("Raw sensor payload tuple cannot be None")
        (
            plant_id,
            sensor_id,
            timestamp,
            value,
            unit,
            topic,
            correlation_id,
        ) = values
        topic_enum = Topics(str(topic))
        return cls(
            plant_id=plant_id,
            sensor_id=sensor_id,
            timestamp=timestamp,
            value=value,
            unit=unit,
            topic=topic_enum,
            correlation_id=correlation_id,
        )

    @classmethod
    def from_row(cls, row):
        """Create a RawSensorData instance from a PySpark Row object.

        This class method constructs a RawSensorData instance using data
        extracted from a PySpark Row object. It maps the fields of the Row
        to the corresponding attributes of the dataclass.

        Parameters
        ----------
        row : pyspark.sql.Row
            A PySpark Row object containing the raw sensor data.

        Returns
        -------
        RawSensorData
            An instance of RawSensorData populated with data from the Row.
        """
        topic_value = str(getattr(row, "topic"))
        topic = Topics(topic_value)
        return cls(
            plant_id=getattr(row, "plant_id"),
            sensor_id=getattr(row, "sensor_id"),
            timestamp=getattr(row, "timestamp"),
            value=getattr(row, "value"),
            unit=getattr(row, "unit"),
            topic=topic,
            correlation_id=getattr(row, "correlation_id"),
        )
