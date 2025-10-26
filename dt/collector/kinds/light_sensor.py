import adafruit_bh1750
import board
from typing_extensions import override

from dt.collector.kinds.base_sensor import Pin, Sensor
from dt.communication import Topics


class LightSensor(Sensor):
    """Represents a BH1750 light sensor.

    This class interfaces with a BH1750 light sensor to read ambient light
    intensity in lux. It communicates with the sensor over the I2C bus.

    Parameters
    ----------
    name : str
        The name of the sensor.
    read_interval : int
        The interval in seconds at which the sensor should be read.
    pin : board.Pin
        The GPIO pin for the sensor. For I2C sensors like the BH1750, this
        is not directly used in the initialization of the sensor object but
        is required by the base `Sensor` class. The I2C bus is typically
        configured system-wide.
    """

    def __init__(self, name: str, read_interval: int, pin: Pin) -> None:
        super().__init__(name, read_interval, pin)
        self._unit = "lx"
        self._sensor = adafruit_bh1750.BH1750(board.I2C())

        self.logger.info(f"Initialized {self.name} on I2C bus.")

    @property
    @override
    def unit(self) -> str:
        return self._unit

    @property
    @override
    def topic(self) -> Topics:
        return Topics.LIGHT_INTENSITY

    @override
    def read_sensor(self) -> float:
        self.logger.info("Reading light intensity...")
        light_intensity = self._sensor.lux
        if light_intensity is None:
            self.logger.error("Failed to read light intensity.")
            return -1
        else:
            self.logger.info(f"Light intensity: {light_intensity} lx")
        return light_intensity
