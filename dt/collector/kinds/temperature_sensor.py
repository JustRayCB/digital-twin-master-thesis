from typing import Any

from typing_extensions import override

from dt.collector.kinds.base_sensor import Pin, Sensor
from dt.collector.kinds.dht22_sensor import DHT22Device
from dt.communication.topics import Topics


class TemperatureSensor(Sensor):
    """Represents a temperature sensor, specifically using a DHT22 sensor.

    This class interfaces with a DHT22 sensor to read temperature data. It
    shares a `DHT22Device` with the humidity stream so both logical sensors
    read from the same physical device and use the same recovery policy.

    Parameters
    ----------
    name : str
        The name of the sensor.
    read_interval : int
        The interval in seconds at which the sensor should be read.
    pin : board.Pin
        The GPIO pin to which the DHT22 sensor is connected.
    """

    def __init__(
        self,
        name: str,
        read_interval: int,
        pin: Pin,
        power_pin: Any,
        reboot_after_failures: int = 3,
        power_off_seconds: float = 3.0,
        reboot_wait_seconds: float = 2.0,
        read_retry_count: int = 2,
        read_retry_delay_seconds: float = 2.0,
    ) -> None:
        super().__init__(name, read_interval, pin)
        self._unit = "°C"
        self._sensor = DHT22Device.get_instance(
            data_pin=self.pin,
            power_pin=power_pin,
            reboot_after_failures=reboot_after_failures,
            power_off_seconds=power_off_seconds,
            reboot_wait_seconds=reboot_wait_seconds,
            read_retry_count=read_retry_count,
            read_retry_delay_seconds=read_retry_delay_seconds,
        )

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
    def read_sensor(self) -> float | None:
        temperature_c = self._sensor.read_temperature()
        if temperature_c is not None:
            self.logger.info(f"Temperature: {temperature_c}°C")
            return temperature_c
        return None
