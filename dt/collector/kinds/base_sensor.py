import time
from abc import ABC, abstractmethod

from dt.communication.dataclasses import RawSensorData, SensorDescriptor
from dt.communication.topics import Topics
from dt.utils.ids import new_correlation_id
from dt.utils.logger import get_logger

Pin = int


class Sensor(ABC):
    """Abstract base class for all sensors.

    This class defines the common interface and functionality for all sensors
    in the system. It includes methods for reading data, checking if a new
    reading is needed, and converting the sensor's metadata to a dataclass.
    Subclasses must implement the `unit`, `topic`, `read_sensor` methods.

    Parameters
    ----------
    name : str
        The name of the sensor.
    read_interval : int
        The interval in seconds at which the sensor should be read.
    pin : board.Pin
        The GPIO pin to which the sensor is connected.

    Attributes
    ----------
    sensor_id : int
        The unique ID assigned to the sensor by the database. Initialized to -1.
    name : str
        The name of the sensor.
    pin : board.Pin
        The GPIO pin where the sensor is connected.
    read_interval : int
        The interval in seconds between sensor readings.
    last_data : float
        The last processed data value read from the sensor.
    last_read_time : float
        The timestamp of the last sensor reading.
    logger : logging.Logger
        The logger for this sensor instance.
    """

    def __init__(self, name: str, read_interval: int, pin: int, plant_id: int = 1) -> None:
        self.sensor_id: int = -1  # Assigned by the database
        self.plant_id: int = plant_id
        self.name: str = name
        self.pin: int = pin
        self.read_interval: int = read_interval
        self._unit: str = ""

        self.last_data: float = -1
        self.last_read_time: float = -1

        self.logger = get_logger(__name__)

    @property
    @abstractmethod  # Use this decorator to ensure not to forget to change the unit  of each sensor
    def unit(self) -> str:
        """Get the unit of measurement for the sensor.

        This is an abstract property that must be implemented by subclasses.

        Returns
        -------
        str
            The unit of measurement (e.g., "Celsius", "%").
        """
        raise NotImplementedError(f"Property unit not implemented for {self.name}")

    @property
    @abstractmethod
    def topic(self) -> Topics:
        """Get the messaging topic for the sensor's data.

        This is an abstract property that must be implemented by subclasses.

        Returns
        -------
        Topics
            The topic where the sensor data should be published.
        """
        raise NotImplementedError(f"Property topic not implemented for {self.name}")

    def needs_data(self, time) -> bool:
        """Check if the sensor needs to be read based on the read interval.

        Parameters
        ----------
        current_time : float
            The current time as a Unix timestamp.

        Returns
        -------
        bool
            True if the time since the last reading is greater than or
            equal to the read interval, False otherwise.
        """
        return (
            time - self.last_read_time >= self.read_interval if self.last_read_time != -1 else True
        )

    def read(self) -> RawSensorData | None:
        """Read data from the sensor and return it as a RawSensorData object.

        This method reads the raw data from the sensor, processes it, updates
        the last read time and data, and returns a `SensorData` object
        containing the processed value and metadata.

        Returns
        -------
        RawSensorData | None
            A dataclass object containing the sensor data and metadata, or None
            when the sensor does not return a value.
        """
        current_time = time.time()
        raw_value = self.read_sensor()

        self.last_read_time = current_time
        if raw_value is None:
            self.logger.error(f"Failed to read {self.name}: no data returned")
            return None

        self.last_data = raw_value

        # assert self.id != -1, "Sensor ID not set"

        data = RawSensorData(
            plant_id=self.plant_id,
            sensor_id=self.sensor_id,
            timestamp=current_time,
            value=raw_value,
            unit=self.unit,
            topic=self.topic,
            correlation_id=new_correlation_id(),
        )

        return data

    @abstractmethod
    def read_sensor(self) -> float | None:
        """Read the raw value from the sensor.

        This is an abstract method that must be implemented by subclasses.

        Returns
        -------
        float | None
            The raw value read from the sensor, or None if no data is available.
        """
        raise NotImplementedError(f"Method read_sensor not implemented for {self.name}")

    def to_dataclass(self) -> SensorDescriptor:
        """Convert the sensor's metadata to a SensorDescriptor dataclass.

        Returns
        -------
        SensorDescriptor
            A dataclass object containing the sensor's metadata.
        """
        try:
            pin_id = int(str(self.pin))
        except ValueError:
            self.logger.error(f"Invalid pin value: {self.pin}")
            pin_id = -2
        return SensorDescriptor(
            id=self.sensor_id,
            plant_id=self.plant_id,
            name=self.name,
            read_interval=self.read_interval,
            pin=pin_id,
        )
