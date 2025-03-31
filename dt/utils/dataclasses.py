import json
from dataclasses import dataclass

from typing_extensions import Union

from dt.communication.topics import MQTTTopics


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
        self.topic = MQTTTopics(self.topic)

    def to_json(self) -> str:
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, json_data: Union[str, dict]):
        if isinstance(json_data, str):
            data = json.loads(json_data)
        elif isinstance(json_data, dict):
            data = json_data
        else:
            raise TypeError("json_data must be a str or dict")
        return cls(**data)

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

    @staticmethod
    def validate_json(json_data: str) -> bool:
        try:
            data = json.loads(json_data)
            assert all(
                key in data for key in SensorData.__annotations__.keys()
            ), "Missing keys in JSON data"
            assert isinstance(data["sensor_id"], int), "sensor_id must be an int"
            assert isinstance(data["timestamp"], (int, float)), "timestamp must be a float"
            assert isinstance(data["value"], (int, float)), "value must be a float"
            assert isinstance(data["unit"], str), "unit must be a str"
            assert isinstance(data["topic"], str), "topic must be a str"
            # assert data["topic"] in MQTTTopics.__members__, "topic must be a valid MQTT topic"
            return True
        except Exception:
            return False


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

    sensor_id: int
    name: str
    pin: int
    read_interval: int

    def __post_init__(self):
        self.sensor_id = int(self.sensor_id)
        self.name = str(self.name)
        self.pin = int(self.pin)
        self.read_interval = int(self.read_interval)

    def change_id(self, sensor_id: int):
        self.sensor_id = sensor_id

    @classmethod
    def from_json(cls, json_data: Union[str, dict]):
        if isinstance(json_data, str):
            data = json.loads(json_data)
        elif isinstance(json_data, dict):
            data = json_data
        else:
            raise TypeError("json_data must be a str or dict")
        return cls(**data)

    def to_json(self) -> str:
        return json.dumps(self.__dict__)

    @staticmethod
    def validate_json(json_data: str) -> bool:
        try:
            data = json.loads(json_data)
            assert all(
                key in data for key in SensorDataClass.__annotations__.keys()
            ), "Missing keys in JSON data"
            assert isinstance(data["sensor_id"], int), "sensor_id must be an int"
            assert isinstance(data["name"], str), "name must be a str"
            assert isinstance(data["pin"], int), "pin must be an int"
            assert isinstance(data["read_interval"], int), "read_interval must be an int"
            return True
        except Exception:
            return False


@dataclass
class DBTimestampQuery:
    """Represents a query to the database to get the data from a specific timestamp.

    Attributes
    ----------
    from_timestamp : The start timestamp of the query.
    to_timestamp : The end timestamp of the query.
    data_type : The type of data to query.
    """

    from_timestamp: float
    to_timestamp: float
    data_type: str

    def __post_init__(self):
        self.from_timestamp = float(self.from_timestamp)
        self.to_timestamp = float(self.to_timestamp)
        self.data_type = str(self.data_type)

    def to_json(self) -> str:
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, json_data: Union[str, dict]):
        if isinstance(json_data, str):
            data = json.loads(json_data)
        elif isinstance(json_data, dict):
            data = json_data
        else:
            raise TypeError("json_data must be a str or dict")
        return cls(**data)

    @staticmethod
    def validate_json(json_data: str) -> bool:
        try:
            data = json.loads(json_data)
            assert all(
                key in data for key in DBTimestampQuery.__annotations__.keys()
            ), "Missing keys in JSON data"
            assert isinstance(
                data["from_timestamp"], (int, float)
            ), "from_timestamp must be a float"
            assert isinstance(data["to_timestamp"], (int, float)), "to_timestamp must be a float"
            assert isinstance(data["data_type"], str), "data_type must be a str"
            assert data["data_type"] in [
                t.short_name for t in MQTTTopics if t != MQTTTopics._PREFIX_SENSOR
            ], f"Topic {data['topic']} is not a valid MQTT topic"
            return True
        except Exception:
            return False
