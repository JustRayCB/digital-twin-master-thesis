import adafruit_dht
import board
from typing_extensions import override

from dt.collector.kinds.base_sensor import Sensor
from dt.collector.kinds.dht22_sensor import DHT22Singleton
from dt.communication import Topics


class TemperatureSensor(Sensor):
    """DHT22 Temperature/Humidity sensor."""

    def __init__(self, name: str, read_interval: int, pin: "Pin") -> None:
        super().__init__(name, read_interval, pin)
        self._unit = "°C"
        # self._board_pin = board.D23 if pin == 23 else board.D4
        # self._sensor = adafruit_dht.DHT22(self.pin)  # DHT11 or DHT22
        self._sensor = DHT22Singleton.get_instance(self.pin)

        self.logger.info(f"Initialized {self.name} on pin {self.pin}.")

    @property
    @override
    def unit(self) -> str:
        return self._unit

    @property
    @override
    def topic(self) -> Topics:
        return Topics.TEMPERATURE

    @override
    def read_sensor(self) -> float:
        try:
            temperature_c = self._sensor.temperature
            # humidity = self._sensor.humidity # Uncomment if you want to read ambiant humidity
            self.logger.info(f"Temperature: {temperature_c}°C")
            return temperature_c  # pyright: ignore[]

        except RuntimeError as error:
            # Errors happen fairly often, DHT's are hard to read, just keep going
            self.logger.error(f"Failed to read temperature: {error.args[0]}")
            return -1

    @override
    def process_data(self, raw_data: float) -> float:
        return raw_data if raw_data != None else -1
