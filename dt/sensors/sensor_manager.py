from dt.communication import MQTTClient, MQTTTopics

from .kinds.base_sensor import Sensor


class SensorManager:
    """Will manage all the used sensors and get the data on time

    Attributes
    ----------
    sensors : dict
        A dictionary containing all the sensors used in the project

    """

    def __init__(self) -> None:
        self.sensors: dict[str, Sensor] = {}
        self.mqtt_client = MQTTClient(id="sensor_manager")
        self.mqtt_client.connect()

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
        for sensor_name, sensor in self.sensors.items():
            if sensor.needs_data():
                data[sensor.name] = sensor.read()
                self.mqtt_client.publish(
                    MQTTTopics.SENSORS_DATA, data[sensor.name]
                )  # Publish the data to whoever is subscribed to the topic
                # TODO: Publish the data to the corresponding topic e.g. temperature, humidity, etc.
        return data

    def __del__(self):
        self.mqtt_client.disconnect()
