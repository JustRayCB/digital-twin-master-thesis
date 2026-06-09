from __future__ import annotations

import time
from typing import Any

import adafruit_dht
import board
import digitalio

from dt.utils.logger import get_logger


class DHT22Device:
    """Shared controller for one physical DHT22 sensor.

    Temperature and humidity are exposed by the same hardware, so both logical
    streams should reuse one device instance per `(data_pin, power_pin)` pair.
    The controller tracks consecutive read failures and power-cycles the sensor
    through an optional GPIO-controlled supply pin when the failure threshold is
    reached.
    """

    _devices: dict[tuple[str, str | None], DHT22Device] = {}

    def __init__(
        self,
        data_pin: Any,
        power_pin: Any | None = None,
        reboot_after_failures: int = 3,
        power_off_seconds: float = 3.0,
        reboot_wait_seconds: float = 2.0,
        read_retry_count: int = 2,
        read_retry_delay_seconds: float = 2.0,
    ) -> None:
        self.logger = get_logger(__name__)
        self.data_pin = data_pin
        self.power_pin = power_pin
        self.reboot_after_failures = reboot_after_failures
        self.power_off_seconds = power_off_seconds
        self.reboot_wait_seconds = reboot_wait_seconds
        self.read_retry_count = read_retry_count
        self.read_retry_delay_seconds = read_retry_delay_seconds
        self.consecutive_failures = 0
        self._sensor: Any | None = None
        self._power: Any | None = None

        if self.power_pin is not None:
            power_output = self._build_power_output(self.power_pin)
            power_output.value = True
            self._power = power_output
            time.sleep(self.reboot_wait_seconds)

        self._create_sensor()

    @classmethod
    def get_instance(
        cls,
        data_pin: Any,
        power_pin: Any | None = None,
        reboot_after_failures: int = 3,
        power_off_seconds: float = 3.0,
        reboot_wait_seconds: float = 2.0,
        read_retry_count: int = 2,
        read_retry_delay_seconds: float = 2.0,
    ) -> DHT22Device:
        key = (str(data_pin), str(power_pin) if power_pin is not None else None)
        if key not in cls._devices:
            cls._devices[key] = cls(
                data_pin=data_pin,
                power_pin=power_pin,
                reboot_after_failures=reboot_after_failures,
                power_off_seconds=power_off_seconds,
                reboot_wait_seconds=reboot_wait_seconds,
                read_retry_count=read_retry_count,
                read_retry_delay_seconds=read_retry_delay_seconds,
            )
        return cls._devices[key]

    @classmethod
    def reset_instances(cls) -> None:
        for device in cls._devices.values():
            device.dispose()
        cls._devices.clear()

    def read_temperature(self) -> float | None:
        return self._read_measurement("temperature")

    def read_humidity(self) -> float | None:
        return self._read_measurement("humidity")

    def _read_measurement(self, attribute_name: str) -> float | None:
        if self._sensor is None:
            self._create_sensor()

        last_error: RuntimeError | None = None
        for attempt in range(self.read_retry_count + 1):
            try:
                value = getattr(self._sensor, attribute_name)
                if value is None:
                    raise RuntimeError(f"DHT22 {attribute_name} returned None")
                self.consecutive_failures = 0
                return value
            except RuntimeError as error:
                last_error = error
                if attempt < self.read_retry_count:
                    time.sleep(self.read_retry_delay_seconds)

        assert last_error is not None
        self._record_failure(attribute_name, last_error)
        return None

    def _record_failure(self, attribute_name: str, error: RuntimeError) -> None:
        self.consecutive_failures += 1
        self.logger.warning(
            f"Failed to read DHT22 {attribute_name} on {self.data_pin} "
            f"({self.consecutive_failures}/{self.reboot_after_failures}): {error}"
        )
        if self.consecutive_failures >= self.reboot_after_failures and self._power is not None:
            self._power_cycle()

    def _power_cycle(self) -> None:
        self.logger.warning(f"Power cycling DHT22 on {self.data_pin}")
        self._dispose_sensor()

        power_output = self._power
        assert power_output is not None

        try:
            power_output.value = False
            time.sleep(self.power_off_seconds)
        finally:
            power_output.value = True

        time.sleep(self.reboot_wait_seconds)

        self._create_sensor()
        self.consecutive_failures = 0

    def _create_sensor(self) -> None:
        if adafruit_dht is None:
            raise RuntimeError("adafruit_dht is required to use the DHT22 sensor")
        if self._power is not None and not self._power.value:
            self.logger.warning(f"DHT22 power pin was OFF; turning it ON before initialization")
            self._power.value = True
            time.sleep(self.reboot_wait_seconds)
        self.logger.info(f"Initializing DHT22 sensor on data pin {self.data_pin}")
        self._sensor = adafruit_dht.DHT22(self.data_pin)

    def dispose(self) -> None:
        """Release the sensor and the power GPIO."""
        self._dispose_sensor()

        if self._power is not None:
            try:
                self._power.value = False
            finally:
                deinit = getattr(self._power, "deinit", None)
                if callable(deinit):
                    deinit()
                self._power = None

    def _dispose_sensor(self) -> None:
        if self._sensor is None:
            return
        with_exit = getattr(self._sensor, "exit", None)
        if callable(with_exit):
            with_exit()
        self._sensor = None

    def _build_power_output(self, power_pin: Any) -> Any:
        if digitalio is None:
            raise RuntimeError("digitalio is required to control the DHT22 power pin")

        power_output = digitalio.DigitalInOut(power_pin)
        power_output.direction = digitalio.Direction.OUTPUT
        return power_output
