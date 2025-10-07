from dataclasses import dataclass

from dt.communication.dataclasses.serializable import JsonSerializable
from dt.communication.topics import Topics


@dataclass
class SensorData(JsonSerializable):
    """Represents the typical data structure of a sensor data.
    It is used to store the data read from the sensors.
    It is also used to send the data via Messaging Service to the web application and the database.

    Attributes
    ----------
    sensor_id : The id of the sensor that generated the data.
    timestamp : The timestamp when the data was read.
    value : The value read from the sensor.
    unit : The unit of measurement of the sensor.
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
        """
        Returns a dictionary with only the value and the timestamp of the SensorData object
        Currently used to send the data through SocketIO
        """
        return {"value": self.value, "time": self.timestamp}

    @property
    def data_type(self):
        """
        Returns the last part of the topic (sensor's data)
        """
        return self.topic.short_name

    def py_to_js_timestamp(self):
        """
        Converts the timestamp from Python format to JavaScript format
        NOTE: JavaScript uses milliseconds since epoch, while Python uses seconds since epoch
        """
        # Convert the timestamp from seconds to milliseconds
        self.timestamp = self.timestamp * 1000
