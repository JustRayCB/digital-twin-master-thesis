from dataclasses import dataclass

from typing_extensions import override


@dataclass
class SensorDescriptor:
    """Represents a sensor in the system.

    This dataclass defines the metadata for a sensor, including its ID, name,
    the GPIO pin it is connected to, and the interval at which it should be
    read.

    Attributes
    ----------
    id : int
        The unique identifier for the sensor.
    plant_id : int
        The identifier of the plant this sensor is associated with.
    name : str
        The name of the sensor (e.g., "DHT22").
    pin : int
        The GPIO pin number where the sensor is connected.
    read_interval : int
        The interval in seconds between two consecutive readings of the sensor.
    status : str
        Current sensor status (e.g., active, inactive).
    """

    id: int
    plant_id: int
    name: str
    pin: int
    read_interval: int
    status: str = "active"

    def __post_init__(self):
        self.id = int(self.id)
        self.plant_id = int(self.plant_id)
        self.name = str(self.name)
        self.pin = int(self.pin)
        self.read_interval = int(self.read_interval)
        self.status = str(self.status)

    def change_id(self, sensor_id: int):
        """Update the sensor's ID.

        Parameters
        ----------
        sensor_id : int
            The new ID for the sensor.
        """
        self.id = sensor_id
