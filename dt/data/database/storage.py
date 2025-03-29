# dt/data/database/storage.py
import sqlite3
import threading

from dt.communication import MQTTClient, MQTTTopics
from dt.sensors import Sensor
from dt.utils import SensorData, SensorDataClass, get_logger


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

    def insert_data(self, data: SensorData) -> None:
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
                    "INSERT INTO sensors_data (sensor_id, value, unit, timestamp, data_type) VALUES (?, ?, ?, ?)",
                    (
                        data.sensor_id,
                        data.value,
                        data.unit,
                        data.timestamp,
                        data.data_type,
                    ),
                )
                self.conn.commit()
                self.logger.info(f"Successfully inserted data for sensor {data.sensor_id}")
            except Exception as e:
                self.logger.error(f"Error inserting data: {e}")

    def insert_datas(self, datas: dict[str, SensorData]) -> None:
        """Insert read data into the database

        Parameters
        ----------
        datas : dict[str, dict[str, any]]
            Data read from the (multiple) sensors with their metadata
        """
        for data in datas.values():
            self.insert_data(data)

    def get_data(self, sensor_id: int, limit: int = 10) -> list[SensorData]:
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
                datas = cursor.fetchall()
                return [
                    SensorData(
                        sensor_id=data[1],
                        value=data[2],
                        unit=data[3],
                        timestamp=data[4],
                        topic=MQTTTopics.from_short_name(data[5]),
                    )
                    for data in datas
                ]

            except Exception as e:
                self.logger.error(f"Error getting data: {e}")
                return []

    def get_data_from_timestamp(self, data_type: str, start_time: float) -> list[SensorData]:
        """Get the data from a specific timestamp to the current time

        Parameters
        ----------
        data_type : str
            The type of data to retrieve
        start_time : float
            The timestamp from which to retrieve the data

        Returns
        -------
        list[dict[str, any]]
            The data from the database
        """
        # Acquire lock for database operation
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT * FROM sensors_data WHERE data_type = ? AND timestamp >= ?",
                    (data_type, start_time),
                )
                datas = cursor.fetchall()
                return [
                    SensorData(
                        sensor_id=data[1],
                        value=data[2],
                        unit=data[3],
                        timestamp=data[4],
                        topic=MQTTTopics.from_short_name(data[5]),
                    )
                    for data in datas
                ]

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
                return result[0] if result else -1
            except Exception as e:
                self.logger.error(f"Error getting sensor ID: {e}")
                return -1

    def add_sensor(self, sensor: SensorDataClass) -> int:
        """Add a sensor to the database

        Parameters
        ----------
        sensor : Sensor
            The sensor to add

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
                    "INSERT INTO sensors (name, pin, read_interval) VALUES (?, ?, ?)",
                    (sensor.name, sensor.pin, sensor.read_interval),
                )
                self.conn.commit()
                id: int = cursor.lastrowid  # pyright: ignore[]
                self.logger.info(f"Added sensor {sensor.name} with ID {id}")
                assert id > 0, f"Error adding sensor {sensor.name} to the database, ID: {id}"
                return id
            except Exception as e:
                self.logger.error(f"Error adding sensor: {e}")
                return -1

    def bind_sensors(self, sensor: SensorDataClass) -> None:
        """Bind the sensor to the database

        Parameters
        ----------
        sensor : Sensor
            The sensor to bind
        """
        temp_id = self.get_sensor_id(sensor.name)
        if temp_id > 0:  # Already exists in the database
            sensor.change_id(temp_id)
            self.logger.info(f"Bound sensor {sensor.name} to existing ID {sensor.sensor_id}")
        else:
            temp_id = self.add_sensor(sensor)
            sensor.change_id(temp_id)
            assert sensor.sensor_id > 0, "Error Adding sensor to the DB"
            self.logger.info(f"Created new sensor {sensor.name} with ID {sensor.sensor_id}")

    def close(self):
        """Close the database connection"""
        with self.db_lock:
            if self.conn:
                self.conn.close()
                self.logger.info("Database connection closed")


# if __name__ == "__main__":
#     try:
#         storage = Storage()
#         # Keep the main thread alive
#         while True:
#             sleep(1)
#     except KeyboardInterrupt:
#         # Clean shutdown
#         storage.close()
#         print("Storage service shut down gracefully")
