import numpy as np
from typing_extensions import override

from dt.collector.kinds.base_sensor import Sensor
from dt.communication import Topics
from dt.utils.logger import get_logger


class MockMoistureSensor(Sensor):
    def __init__(
        self,
        name: str,
        read_interval: int,
        nb_readings: int,
    ) -> None:
        super().__init__(name, read_interval, -1)
        self.nb_readings = nb_readings
        self.readings: list[float] = []
        self.current_reading = 0

        self.min_value = 200  # (very dry)
        self.max_value = 2000  # (very wet)
        self.logger = get_logger(__name__)

        self.logger.info(f"Initializing MockMoistureSensor with {nb_readings} readings.")
        self._generate_readings()

    def _generate_readings(self) -> None:
        """
        Generate realistic readings for the soil moisture sensor.

        The pattern follows:
        1. A sudden increase in moisture level (plant is watered)
        2. Gradual, natural decrease in moisture level (soil drying over time)
        3. Add realistic noise for sensor imperfection.
        """
        # We can assume that the soil moisture level will decrease over time
        # as the plant absorbs water from the soil.

        # Assume the plant is watered at the beginning
        current_moisture = self.max_value

        decay_rate = 0.01
        noise_level = 50  # Additive noise range [-50, 50]

        for t in range(self.nb_readings):
            if current_moisture > self.min_value:  # Simulate drying over time
                # Exponential decay formula
                current_moisture = self.min_value + (self.max_value - self.min_value) * np.exp(
                    -decay_rate * t
                )
                # Add noise to simulate sensor imperfection
                current_moisture += np.random.uniform(-noise_level, noise_level)
            else:
                # Keep the reading near the minimum value with some noise (simulate plateau)
                current_moisture = self.min_value + np.random.uniform(0, 20)

            # Add the moisture level to the readings list
            self.readings.append(max(self.min_value, min(current_moisture, self.max_value)))
            self.logger.debug(f"Generated reading {self.readings[-1]} at time {t}")

    @property
    @override
    def unit(self) -> str:
        return "%"

    @property
    @override
    def topic(self) -> Topics:
        return Topics.SOIL_MOISTURE

    @override
    def read_sensor(self) -> float:
        if self.current_reading == self.nb_readings:
            self.current_reading = 0
        reading = self.readings[self.current_reading]
        self.current_reading += 1
        self.logger.debug(f"Read sensor value: {reading}")
        return reading

    @override
    def process_data(self, raw_data: float) -> float:
        # Given the raw data in the range [200, 2000], we can normalize it to [0, 100]
        processed_data = (raw_data - self.min_value) / (self.max_value - self.min_value) * 100
        self.logger.debug(f"Processed data: {processed_data} from raw data: {raw_data}")
        return processed_data
