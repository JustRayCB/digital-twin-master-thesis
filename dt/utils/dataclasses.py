import json
from dataclasses import dataclass

from dt.communication import MQTTTopics


@dataclass
class SensorData:
    """Represents the typical data structure of a sensor data.
    It is used to store the data read from the sensors.
    It is also used to send the data via MQTT to the web application and the database.

    Attributes
    ----------
    sensor_id : The id of the sensor that generated the data.
    timestamp : The timestamp when the data was read.
    value : The value read from the sensor.
    unit : The unit of measurement of the sensor.
    """

    sensor_id: int
    timestamp: float
    value: float
    unit: str
    topic: MQTTTopics

    def __post_init__(self):
        self.sensor_id = int(self.sensor_id)
        self.timestamp = float(self.timestamp)
        self.value = float(self.value)
        self.unit = str(self.unit)

    def to_json(self) -> str:
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, json_data: str):
        return cls(**json.loads(json_data))

    def shrink_data(self):
        """
        Returns a dictionary with only the value and the timestamp of the SensorData object
        Currently used to send the data through SocketIO
        """
        return {"value": self.value, "time": self.timestamp}

    @property
    def data_type(self):
        """
        Returns the last part of the MQTT topic (sensor's data)
        """
        return self.topic.short_name


@dataclass
class SensorDataClass:
    """Represents a sensor in the system.

    Attributes
    ----------
    id : The id of the sensor.
    name : The name of the sensor.
    pin : The GPIO pin where the sensor is connected.
    read_interval : The interval in seconds between two reads of the sensor.
    """

    id: int
    name: str
    pin: int
    read_interval: int

    def __post_init__(self):
        self.id = int(self.id)
        self.name = str(self.name)
        self.pin = int(self.pin)
        self.read_interval = int(self.read_interval)

    def change_id(self, sensor_id: int):
        self.id = sensor_id

    @classmethod
    def from_json(cls, json_data: str):
        return cls(**json.loads(json_data))

    def to_json(self) -> str:
        return json.dumps(self.__dict__)

    @staticmethod
    def validate_json(json_data: str) -> bool:
        try:
            data = json.loads(json_data)
            return all(key in data for key in SensorDataClass.__dict__.keys())
        except Exception:
            return False
