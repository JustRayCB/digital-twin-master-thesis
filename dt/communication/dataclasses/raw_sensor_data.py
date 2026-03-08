from dataclasses import dataclass

from dt.communication.topics import Topics


@dataclass
class RawSensorData:
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
