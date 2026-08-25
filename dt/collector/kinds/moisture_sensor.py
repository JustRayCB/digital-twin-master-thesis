import board
from adafruit_seesaw.seesaw import Seesaw
from typing_extensions import override

from dt.collector.kinds.base_sensor import Pin, Sensor
from dt.communication.topics import Topics


class SoilMoistureSensor(Sensor):
    """Represents an Adafruit STEMMA soil moisture sensor.

    This class interfaces with the sensor via the I2C protocol to read soil
    moisture levels. It then normalizes the raw sensor reading to a percentage.

    Parameters
    ----------
    name : str
        The name of the sensor.
    read_interval : int
        The interval in seconds at which the sensor should be read.
    pin : board.Pin
        The GPIO pin for the sensor. For I2C sensors like this one, this
        is not directly used in the initialization of the sensor object but
        is required by the base `Sensor` class. The I2C bus is typically
        configured system-wide.

    """

    def __init__(self, name: str, read_interval: int, pin: Pin, address: int):
        super().__init__(name, read_interval, pin)
        self._unit = "%"
        self._i2c_bus = board.I2C()
        self._address = address
        self._sensor | None = None 

        self.logger.info(f"Initialized {self.name} on pin {self.pin}.")

    def _connect_sensor(self) -> Seesaw | None:
        try:
            return Seesaw(self._i2c_bus, addr=self._address)
        except (OSError, RuntimeError) as error:
            self.logger.error(
                f"Failed to connect {self.name} at I2C address "
                f"{self._address:#04x}: {error}"
            )
            return None

    @property
    @override
    def unit(self) -> str:
        return self._unit

    @property
    @override
    def topic(self) -> Topics:
        return Topics.SOIL_MOISTURE

    @override
    def read_sensor(self) -> float | None:
        if self._sensor is None:
            self._sensor = self._connect_sensor()

        if self._sensor is None:
            return None

        try:
            moisture = self._sensor.moisture_read()
            self.logger.info(f"Read moisture: {moisture}%")
            return moisture
        except (OSError, RuntimeError) as error:
            self.logger.error(f"Failed to read {self.name}: {error}")
            self._sensor = None
            return None

