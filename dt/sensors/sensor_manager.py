from sensors.kinds.base_sensor import Sensor


class SensorManager:
    """Will manage all the used sensors and get the data on time

    Attributes
    ----------
    sensors : dict
        A dictionary containing all the sensors used in the project

    """

    def __init__(self) -> None:
        self.sensors: dict[str, Sensor] = {}

    def add_sensor(self, sensor: Sensor) -> None:
        self.sensors[sensor.name] = sensor

    def remove_sensor(self, sensor_name: str) -> None:
        if sensor_name in self.sensors:
            del self.sensors[sensor_name]

    def read_all_sensors(self) -> dict[str, dict[str, any]]:
        """Read data from all the sensors that needs to be read

        Returns
        -------
        dict
            A dictionary containing the data from all the sensors that needs to be read

        """
        data = {}
        for sensor in self.sensors.values():
            if sensor.needs_data():
                data[sensor.name] = sensor.read()
        return data
