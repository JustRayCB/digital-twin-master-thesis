import json
from abc import ABC
from dataclasses import asdict, dataclass
from typing import Any, Dict, TypeVar, Union

from dt.communication.topics import Topics

T = TypeVar("T", bound="JsonSerializable")


@dataclass
class JsonSerializable(ABC):
    """
    Abstract base for message/query records:
    - consistent to_dict / to_json (with Enum-safe conversion)
    - from_dict / from_json
    - lightweight required-field validation
    """

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls: type[T], data: Dict[str, Any]) -> T:
        converted: Dict[str, Any] = {}
        for field, field_type in cls.__annotations__.items():
            if field not in data:
                raise ValueError(f"Missing field: {field}")
            value = data[field]
            if isinstance(field_type, type):
                converted[field] = field_type(value)
            else:
                converted[field] = value
        return cls(**converted)

    @classmethod
    def from_json(cls: type[T], json_data: Union[str, Dict[str, Any]]) -> T:
        data = json_data
        if isinstance(data, str):
            data = json.loads(json_data)  # type: ignore
        return cls.from_dict(data)

    @classmethod
    def validate_json(cls: type[T], json_data: Union[str, Dict[str, Any]]) -> bool:
        try:
            cls.from_json(json_data)
        except Exception:
            return False
        return True


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

    sensor_id: int
    timestamp: float
    value: float
    unit: str
    topic: Topics

    def __post_init__(self):
        self.sensor_id = int(self.sensor_id)
        self.timestamp = float(self.timestamp)
        self.value = float(self.value)
        self.unit = str(self.unit)
        self.topic = Topics(self.topic)

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


@dataclass
class SensorDataClass(JsonSerializable):
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


@dataclass
class DBTimestampQuery(JsonSerializable):
    """Represents a query to the database to get the data from a specific timestamp.

    Attributes
    ----------
    from_timestamp : The start timestamp of the query.
    to_timestamp : The end timestamp of the query.
    data_type : The type of data to query.
    """

    data_type: str
    from_timestamp: float
    to_timestamp: float

    def __post_init__(self):
        self.data_type = str(self.data_type)
        self.from_timestamp = float(self.from_timestamp)
        self.to_timestamp = float(self.to_timestamp)

    def js_to_py_timestamp(self):
        """
        Converts the timestamp from JavaScript format to Python format
        """
        # Convert the timestamp from milliseconds to seconds
        self.from_timestamp = self.from_timestamp / 1000
        self.to_timestamp = self.to_timestamp / 1000


@dataclass
class DBIdQuery(JsonSerializable):
    """Represents a query to the database to get the data from a specific sensor id.

    Attributes
    ----------
    sensor_id : The id of the sensor.
    limit : The maximum number of data points to return.
    """

    sensor_id: int
    limit: int

    def __post_init__(self):
        self.sensor_id = int(self.sensor_id)
        self.limit = int(self.limit)
        if self.limit < 1:
            raise ValueError("Limit must be greater than 0")
        if self.sensor_id < 1:
            raise ValueError("Sensor id must be greater than 0")
