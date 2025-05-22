import adafruit_dht
import board
from typing_extensions import override

from dt.communication import Topics
from dt.sensors.kinds.base_sensor import Sensor
from dt.sensors.kinds.dht22_sensor import DHT22Singleton


class HumiditySensor(Sensor):
    """DHT22 Temperature/Humidity sensor."""

    def __init__(self, name: str, read_interval: int, pin: "Pin") -> None:
        super().__init__(name, read_interval, pin)
        self._unit = "%"
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
        return Topics.HUMIDITY

    @override
    def read_sensor(self) -> float:
        try:
            humidity = self._sensor.humidity
            self.logger.info(f"Humidity : {humidity}%")
            return humidity  # pyright: ignore[]

        except RuntimeError as error:
            # Errors happen fairly often, DHT's are hard to read, just keep going
            self.logger.error(f"Failed to read humidity: {error.args[0]}")
            return -1

    @override
    def process_data(self, raw_data: float) -> float:
        return raw_data if raw_data != None else -1
