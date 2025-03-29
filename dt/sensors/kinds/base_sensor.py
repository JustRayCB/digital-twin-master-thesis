import time
from abc import ABC, abstractmethod

from dt.communication import MQTTTopics
from dt.utils import SensorData
from dt.utils.dataclasses import SensorDataClass


class Sensor(ABC):
    """Abstract class that represent a sensor and all basic methods that a sensor should have.

    Attributes
    ----------
    name : str
        Name of the sensor.
    pin : int
        Pin where the sensor is connected.
    read_interval : int
        Interval in seconds that the sensor should be read.

    """

    def __init__(self, name: str, read_interval: int, pin: int) -> None:
        self.id: int = -1  # Assigned by the database
        self.name: str = name
        self.pin: int = pin
        self.read_interval: int = read_interval
        self._unit: str = ""

        self.last_data: float = -1
        self.last_read_time: float = -1

    @property
    @abstractmethod  # Use this decorator to ensure not to forget to change the unit  of each sensor
    def unit(self) -> str:
        """
        Returns
        -------
        str
            The unit of measurement of the sensor.

        """
        raise NotImplementedError(f"Property unit not implemented for {self.name}")

    @property
    @abstractmethod
    def mqtt_topic(self) -> MQTTTopics:
        """
        Returns
        -------
        str
            The MQTT topic where the sensor data should be published.

        """
        raise NotImplementedError(f"Property mqtt_topic not implemented for {self.name}")

    def needs_data(self) -> bool:
        """Check if the sensor needs to be read.

        Returns
        -------
        bool
            True if the sensor needs to be read, False otherwise.

        """
        return (
            time.time() - self.last_read_time >= self.read_interval
            if self.last_read_time != -1
            else True
        )

    def read(self) -> SensorData:
        """Reads the sensor

        Returns
        -------
        dict[str, any]
            Data read with all the metadata (name, timestamp, value, raw_value, unit)

        """
        current_time = time.time()
        raw_value = self.read_sensor()
        processed_value = self.process_data(raw_value)

        self.last_data = processed_value
        self.last_read_time = current_time

        # assert self.id != -1, "Sensor ID not set"

        data = SensorData(
            sensor_id=self.id,
            timestamp=current_time,
            value=processed_value,
            unit=self.unit,
            topic=self.mqtt_topic,
        )

        return data

    @abstractmethod
    def read_sensor(self) -> float:
        """Read the sensor and return the raw value.

        Returns
        -------
        float
            The raw value of the sensor.

        """
        raise NotImplementedError(f"Method read_sensor not implemented for {self.name}")

    @abstractmethod
    def process_data(self, raw_data: float) -> float:
        """Process the raw data from the sensor to ensure that it is in the correct format.

        Parameters
        ----------
        raw_data : float
            The raw data from the sensor.

        Returns
        -------
        float
            The processed data.
        """
        raise NotImplementedError(f"Method process_data not implemented for {self.name}")

    def to_dataclass(self) -> SensorDataClass:
        """Convert the sensor to a dataclass.

        Returns
        -------
        SensorDataClass
            The sensor as a dataclass.

        """
        return SensorDataClass(
            sensor_id=self.id,
            name=self.name,
            read_interval=self.read_interval,
            pin=self.pin,
        )
