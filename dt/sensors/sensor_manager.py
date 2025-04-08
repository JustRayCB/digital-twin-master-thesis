import requests

from dt.communication import (KafkaService, MessagingService, MQTTService,
                              Topics)
from dt.utils import SensorData, SensorDataClass
from dt.utils.logger import get_logger

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
        self.messaging_service: MessagingService = KafkaService(client_id="sensor_manager")
        self.messaging_service.connect()

        self.logger = get_logger(__name__)
        self.logger.info("SensorManager initialized.")

    def add_sensor(self, sensor: Sensor) -> None:
        # TODO: Bind the sensor the the Database
        self.bind_sensor(sensor)
        self.sensors[sensor.name] = sensor
        self.logger.info(f"Added sensor {sensor.name} to the SensorManager.")

    def bind_sensor(self, sensor: Sensor) -> None:
        db_url = "http://localhost:5001/bind_sensor"
        sensor_dataclass: SensorDataClass = sensor.to_dataclass()
        sensor_json = sensor_dataclass.to_json()
        response = requests.post(db_url, json=sensor_json)
        if response.status_code == 200:
            new_id: int = response.json().get("sensor_id")
            sensor.sensor_id = new_id
            self.logger.info(f"Sensor {sensor.name} bound to the database successfully.")
        else:
            self.logger.error(
                f"Failed to bind sensor {sensor.name} to the database: {response.text}"
            )

    def remove_sensor(self, sensor_name: str) -> None:
        if sensor_name in self.sensors:
            self.logger.info(f"Removed sensor {sensor_name} from the SensorManager.")
            del self.sensors[sensor_name]

    def read_all_sensors(self) -> dict[str, SensorData]:
        """Read data from all the sensors that needs to be read

        Returns
        -------
        dict
            A dictionary containing the data from all the sensors that needs to be read

        """
        data: dict[str, SensorData] = {}
        for sensor_name, sensor in self.sensors.items():
            if sensor.needs_data():
                data[sensor.name] = sensor.read()
                topic: Topics = sensor.topic
                self.messaging_service.publish(
                    topic.raw, data[sensor.name]
                )  # Publish the data to whoever is subscribed to the topic
                self.logger.info(f"Published data from {sensor_name} to {topic}.")
                self.logger.debug(f"Data: {data[sensor.name]}")

        return data

    def __del__(self):
        self.logger.info("Disconnecting Messaging Service client in SensorManager.")
        self.messaging_service.disconnect()
