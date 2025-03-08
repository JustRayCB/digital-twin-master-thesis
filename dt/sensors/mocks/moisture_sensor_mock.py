from typing import override

from dt.sensors.kinds.base_sensor import Sensor


class MockMoistureSensor(Sensor):
    def __init__(
        self,
        name: str,
        read_interval: int,
        nb_readings: int,
    ) -> None:
        super().__init__(name, read_interval, -1)
        self._generate_readings()
        self.nb_readings = nb_readings
        self.readings: list[float] = []
        self.current_reading = 0

    def _generate_readings(self) -> None:
        """Generate random readings for the sensor."""
        pass

    @property
    @override
    def unit(self) -> str:
        return "%"

    @override
    def read_sensor(self) -> float:
        if self.current_reading == self.nb_readings:
            self.current_reading = 0
        reading = self.readings[self.current_reading]
        self.current_reading += 1
        return reading

    @override
    def process_data(self, raw_data: float) -> float:
        return raw_data
