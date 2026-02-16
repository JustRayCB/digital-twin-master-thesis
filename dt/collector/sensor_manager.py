import time

from dt.communication.dataclasses import RawSensorData
from dt.communication.db_client import DatabaseApiClient
from dt.communication.messaging_service import KafkaService, MessagingService
from dt.communication.topics import Topics
from dt.utils.exceptions import BadSensorBindingException
from dt.utils.logger import get_logger

from .kinds.base_sensor import Sensor


class SensorManager:
    """Manages sensors, reads data, and publishes it to a messaging service.

    This class is responsible for adding, removing, and reading data from
    various sensors. It checks each sensor to see if it's time for a new
    reading based on its configured interval, and if so, it reads the data
    and publishes it to the appropriate Kafka topic.

    Attributes
    ----------
    sensors : dict[str, Sensor]
        A dictionary of sensor objects, keyed by their names.
    messaging_service : MessagingService
        The client for the messaging service (e.g., Kafka).
    logger : logging.Logger
        The logger for this class.
    db_client : DatabaseApiClient
        The client for interacting with the database API.
    """

    def __init__(self) -> None:
        """Initializes the SensorManager.

        This sets up the sensor dictionary, connects to the messaging service,
        and initializes the database API client.
        """
        self.sensors: dict[str, Sensor] = {}
        self.messaging_service: MessagingService = KafkaService(client_id="sensor_manager")
        self.messaging_service.connect()

        self.logger = get_logger(__name__)
        self.logger.info("SensorManager initialized.")

        self.db_client: DatabaseApiClient = DatabaseApiClient()

    def add_sensor(self, sensor: Sensor) -> None:
        """Add a sensor to the manager.

        Parameters
        ----------
        sensor : Sensor
            The sensor object to be added.
        """
        self.bind_sensor(sensor)  # TODO: Uncomment when binding is stable
        self.sensors[sensor.name] = sensor
        self.logger.info(f"Added sensor {sensor.name} to the SensorManager.")

    def bind_sensor(self, sensor: Sensor) -> None:
        """Bind a sensor to the database to get a unique ID.

        Parameters
        ----------
        sensor : Sensor
            The sensor object to be bound.

        Raises
        ------
        BadSensorBindingException
            If the sensor fails to bind to the database.
        """
        self.logger.info(f"Binding sensor {sensor.name} to the database.")

        sensor_id = self.db_client.bind_sensor(sensor.to_dataclass())
        if sensor_id != -1:
            sensor.sensor_id = sensor_id
            self.logger.info(f"Sensor {sensor.name} bound to the database successfully.")
        else:
            self.logger.error(f"Failed to bind sensor {sensor.name} to the database: {sensor_id}")
            raise BadSensorBindingException(
                f"Failed to bind sensor {sensor.name} to the database: {sensor_id}"
            )

    def remove_sensor(self, sensor_name: str) -> None:
        """Remove a sensor from the manager.

        Parameters
        ----------
        sensor_name : str
            The name of the sensor to be removed.
        """
        if sensor_name in self.sensors:
            self.logger.info(f"Removed sensor {sensor_name} from the SensorManager.")
            del self.sensors[sensor_name]

    def seconds_until_next_read(
        self, current_time: float | None = None, default_sleep_seconds: float = 1.0
    ) -> float:
        """Return seconds until the next sensor is due for a reading.

        This supports best-effort scheduling in a single-threaded loop by allowing the
        caller to sleep until the earliest next-due time across all sensors.

        Parameters
        ----------
        current_time : float | None, optional
            The current time in seconds since the epoch. If None, the current system time
            will be used. Default is None.
        default_sleep_seconds : float, optional
            The default number of seconds to return if there are no sensors managed. Default is 1.0.

        Returns
        -------
        float
            The number of seconds until the next sensor is due for a reading.
        """
        if not self.sensors:
            return default_sleep_seconds

        now = current_time if current_time is not None else time.time()
        seconds_until_due: list[float] = []
        for sensor in self.sensors.values():
            if sensor.last_read_time == -1:  # Never read before
                return 0.0  # Read immediately

            # Calculate when the sensor is next due for a reading
            due_at = sensor.last_read_time + sensor.read_interval
            # Append the time until due to the list
            seconds_until_due.append(max(0.0, due_at - now))

        # Return the minimum time until the next due reading
        return min(seconds_until_due) if seconds_until_due else default_sleep_seconds

    def read_all_sensors(self) -> dict[str, RawSensorData]:
        """Read data from all sensors that are due for a reading.

        This method iterates through all managed sensors, checks if a new
        reading is needed based on the current time and the sensor's read
        interval, reads the data, and publishes it when a value is returned.

        Returns
        -------
        dict[str, SensorData]
            A dictionary containing the data from all sensors that were read,
            keyed by sensor name.
        """
        data: dict[str, RawSensorData] = {}
        for sensor_name, sensor in self.sensors.items():
            current_time = time.time()
            if sensor.needs_data(current_time):
                reading = sensor.read()
                if reading is None:
                    self.logger.warning(f"Skipping publish for {sensor_name}: no data returned.")
                    continue

                data[sensor.name] = reading
                topic = sensor.topic.raw
                self.messaging_service.publish(
                    topic, data[sensor.name]
                )  # Publish the data to whoever is subscribed to the topic
                self.logger.info(f"Published data from {sensor_name} to {topic}.")
                self.logger.debug(f"Data: {data[sensor.name]}")

        return data

    def __del__(self):
        """Clean up resources when the SensorManager is deleted.

        This ensures that the connection to the messaging service is properly
        closed.
        """
        self.logger.info("Disconnecting Messaging Service client in SensorManager.")
        self.messaging_service.disconnect()
