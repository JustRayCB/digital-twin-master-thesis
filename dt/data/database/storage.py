# dt/data/database/storage.py
import sqlite3
import threading
from time import sleep

from dt.communication import MQTTClient, MQTTTopics
from dt.sensors import Sensor
from dt.utils.logger import get_logger


class Storage:
    def __init__(self) -> None:
        self.db_path = "plant_dt.db"
        # Create a single connection
        # No need to check thread safety as we are using mutex
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        # Enable foreign keys support
        self.conn.execute("PRAGMA foreign_keys = ON")

        # Create a mutex for thread synchronization
        self.db_lock = threading.Lock()

        self.logger = get_logger(__name__)

        # Initialize table
        self.create_table()

        # Set up MQTT client
        self.mqtt_client = MQTTClient(hostname="192.168.129.7", id="database")
        self.mqtt_client.connect()

        # Subscribe to the topic where the data is published
        self.mqtt_client.subscribe(MQTTTopics.SOIL_MOISTURE, self.insert_data)

    def create_table(self) -> None:
        """Create the table to store the data"""
        # Acquire lock for database operation
        with self.db_lock:
            cursor = self.conn.cursor()

            # I already have a db_init.sql file, so I will use it to create the table
            dir_path = "/".join(__file__.split("/")[:-1])
            try:
                with open(f"{dir_path}/db_init.sql", "r") as f:
                    cursor.executescript(f.read())
                    self.conn.commit()
                    self.logger.info("Database tables created successfully")
            except Exception as e:
                self.logger.error(f"Error creating database tables: {e}")

    def insert_data(self, data: dict[str, any]) -> None:
        """Insert read data into the database

        Parameters
        ----------
        data : dict[str, any]
            Data read from a (one) sensor with their metadata
        """
        self.logger.debug(f"Received data in thread {threading.get_ident()}: {data}")

        # Acquire lock for database operation
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "INSERT INTO sensors_data (sensor_id, value, unit, timestamp) VALUES (?, ?, ?, ?)",
                    (data["sensor_id"], data["value"], data["unit"], data["timestamp"]),
                )
                self.conn.commit()
                self.logger.info(f"Successfully inserted data for sensor {data['sensor_id']}")
            except Exception as e:
                self.logger.error(f"Error inserting data: {e}")

    def insert_datas(self, datas: dict[str, dict[str, any]]) -> None:
        """Insert read data into the database

        Parameters
        ----------
        datas : dict[str, dict[str, any]]
            Data read from the (multiple) sensors with their metadata
        """
        for data in datas.values():
            self.insert_data(data)

    def get_data(self, sensor_id: int, limit: int = 10) -> list[dict[str, any]]:
        """Get the last data read from a sensor

        Parameters
        ----------
        sensor_id : int
            The id of the sensor
        limit : int, optional
            The number of data to retrieve, by default 10

        Returns
        -------
        list[dict[str, any]]
            The last data read from the sensor
        """
        # Acquire lock for database operation
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT * FROM sensors_data WHERE sensor_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (sensor_id, limit),
                )
                return cursor.fetchall()
            except Exception as e:
                self.logger.error(f"Error getting data: {e}")
                return []

    def get_sensor_id(self, sensor_name: str) -> int:
        """Get the id of a sensor

        Parameters
        ----------
        sensor_name : str
            The name of the sensor

        Returns
        -------
        int
            The id of the sensor
        """
        # Acquire lock for database operation
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT id FROM sensors WHERE name = ?",
                    (sensor_name,),
                )
                result = cursor.fetchone()
                return result
            except Exception as e:
                self.logger.error(f"Error getting sensor ID: {e}")
                return -1

    def add_sensor(self, sensor: Sensor) -> None:
        """Add a sensor to the database

        Parameters
        ----------
        sensor : Sensor
            The sensor to add
        """
        # Acquire lock for database operation
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "INSERT INTO sensors (name) VALUES (?)",
                    (sensor.name,),
                )
                self.conn.commit()
                sensor.id = cursor.lastrowid  # pyright: ignore[]
                assert sensor.id > 0, "Sensor ID not set"
                self.logger.info(f"Added sensor {sensor.name} with ID {sensor.id}")
            except Exception as e:
                self.logger.error(f"Error adding sensor: {e}")

    def bind_sensors(self, sensor: Sensor) -> None:
        """Bind the sensor to the database

        Parameters
        ----------
        sensor : Sensor
            The sensor to bind
        """
        temp_id = self.get_sensor_id(sensor.name)
        if temp_id:
            sensor.id = temp_id
            self.logger.info(f"Bound sensor {sensor.name} to existing ID {sensor.id}")
        else:
            self.add_sensor(sensor)
            self.logger.info(f"Created new sensor {sensor.name} with ID {sensor.id}")

    def close(self):
        """Close the database connection"""
        with self.db_lock:
            if self.conn:
                self.conn.close()
                self.logger.info("Database connection closed")


if __name__ == "__main__":
    try:
        storage = Storage()
        # Keep the main thread alive
        while True:
            sleep(1)
    except KeyboardInterrupt:
        # Clean shutdown
        storage.close()
        print("Storage service shut down gracefully")
