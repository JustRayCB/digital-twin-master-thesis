import time

from typing_extensions import override

from dt.collector.kinds.base_sensor import Pin, Sensor
from dt.collector.kinds.dht22_sensor import DHT22Singleton
from dt.communication.topics import Topics


class HumiditySensor(Sensor):
    """Represents a humidity sensor, specifically using a DHT22 sensor.

    This class interfaces with a DHT22 sensor to read humidity data. It
    utilizes the `DHT22Singleton` to ensure that there is only one instance
    of the sensor object, even if both temperature and humidity are read
    from the same physical device.

    Parameters
    ----------
    name : str
        The name of the sensor.
    read_interval : int
        The interval in seconds at which the sensor should be read.
    pin : board.Pin
        The GPIO pin to which the DHT22 sensor is connected.
    """

    def __init__(self, name: str, read_interval: int, pin: Pin) -> None:
        super().__init__(name, read_interval, pin)
        self._unit = "%"
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
            try:
                for _ in range(2):  # Retry up to 5 times
                    time.sleep(2)  # Wait a bit before retrying
                    humidity = self._sensor.humidity
                    if humidity is not None:
                        self.logger.info(f"Humidity (after retry): {humidity}%")
                        return humidity  # pyright: ignore[]
            except RuntimeError as retry_error:
                self.logger.error(f"Failed to read humidity after retry: {retry_error.args[0]}")
