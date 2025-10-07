from dataclasses import dataclass

from dt.communication.dataclasses.serializable import JsonSerializable
from dt.communication.topics import Topics


@dataclass
class SensorDescriptor(JsonSerializable):
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
