import numpy as np
from typing_extensions import override

from dt.collector.kinds.base_sensor import Sensor
from dt.communication.topics import Topics
from dt.utils.logger import get_logger


class MockMoistureSensor(Sensor):
    """A mock soil moisture sensor for testing and development.

    This class simulates the behavior of a soil moisture sensor by generating
    a realistic pattern of data. The pattern consists of a sudden increase
    in moisture (simulating watering) followed by a gradual, exponential
    decrease as the soil dries out. Random noise is added to make the
    readings appear more realistic.

    This allows for testing of the data processing and visualization
    components without requiring a physical sensor.

    Parameters
    ----------
    name : str
        The name of the sensor.
    read_interval : int
        The interval in seconds at which the sensor should be read.
    nb_readings : int
        The total number of mock readings to generate before the cycle
        repeats.
    """

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
        """Generate a series of realistic soil moisture readings.

        The generated pattern simulates a plant being watered, resulting in a
        high moisture level, followed by an exponential decay as the soil
        dries over time. Realistic noise is added to simulate sensor
        imperfections.
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
