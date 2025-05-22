import board
import busio
from adafruit_seesaw.seesaw import Seesaw
from typing_extensions import override

from dt.communication import Topics
from dt.sensors.kinds.base_sensor import Sensor


class SoilMoistureSensor(Sensor):
    """AddaFruit Stemma Soil Moisture Sensor"""

    def __init__(self, name: str, read_interval: int, pin: "Pin") -> None:
        super().__init__(name, read_interval, pin)
        self._unit = "%"
        self._i2c_bus = busio.I2C(board.D1, board.D0)
        self._sensor = Seesaw(self._i2c_bus, addr=0x36)

        self.min_value = 200  # Minimum value for the sensor
        self.max_value = 2000

        self.logger.info(f"Initialized {self.name} on pin {self.pin}.")

    @property
    @override
    def unit(self) -> str:
        return self._unit

    @property
    @override
    def topic(self) -> Topics:
        return Topics.SOIL_MOISTURE

    @override
    def read_sensor(self) -> float:
        try:
            moisture = self._sensor.moisture_read()
            # temp = self._sensor.get_temp() # Uncomment if you want to read soil temperature
            self.logger.info(f"Read moisture: {moisture}%")
        except RuntimeError as error:
            # Errors happen fairly often, just keep going
            self.logger.error(f"Failed to read moisture: {error}")
            return -1
        return moisture

    @override
    def process_data(self, raw_data: float) -> float:
        # Given the raw data in the range [200, 2000], we can normalize it to [0, 100]
        processed_data = (raw_data - self.min_value) / (self.max_value - self.min_value) * 100
        self.logger.info(f"Processed moisture: {processed_data}%")
        return processed_data
