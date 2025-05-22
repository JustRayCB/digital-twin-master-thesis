import adafruit_bh1750
import board
from board import Pin
from typing_extensions import override

from dt.communication import Topics
from dt.sensors.kinds.base_sensor import Sensor


class LightSensor(Sensor):
    """BH1750 light sensor."""

    def __init__(self, name: str, read_interval: int, pin: Pin) -> None:
        super().__init__(name, read_interval, pin)
        self._unit = "lx"
        self._sensor = adafruit_bh1750.BH1750(board.I2C())

        self.logger.info(f"Initialized {self.name} on pin {self.pin}.")

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

    @override
    def process_data(self, raw_data: float) -> float:
        return raw_data
