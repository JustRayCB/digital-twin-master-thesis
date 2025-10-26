from dataclasses import dataclass

from dt.communication.dataclasses.serializable import JsonSerializable


@dataclass
class SensorDescriptor(JsonSerializable):
    """Represents a sensor in the system.

    This dataclass defines the metadata for a sensor, including its ID, name,
    the GPIO pin it is connected to, and the interval at which it should be
    read.

    Attributes
    ----------
    sensor_id : int
        The unique identifier for the sensor.
    name : str
        The name of the sensor (e.g., "DHT22").
    pin : int
        The GPIO pin number where the sensor is connected.
    read_interval : int
        The interval in seconds between two consecutive readings of the sensor.
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
        """Update the sensor's ID.

        Parameters
        ----------
        sensor_id : int
            The new ID for the sensor.
        """
        self.sensor_id = sensor_id
