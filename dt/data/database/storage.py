import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from typing_extensions import override

from dt.communication import Topics
from dt.utils import Config, SensorData, SensorDescriptor, get_logger


class Storage(ABC):
    """Abstract base class for storage implementations"""

    @abstractmethod
    def create_table(self) -> None:
        """Initialize storage schema"""
        pass

    @abstractmethod
    def insert_data(self, data: SensorData) -> None:
        """Insert a single sensor data reading"""
        pass

    @abstractmethod
    def insert_datas(self, datas: dict[str, SensorData]) -> None:
        """Insert multiple sensor data readings"""
        pass

    @abstractmethod
    def get_data(self, sensor_id: int, limit: int = 10) -> list[SensorData]:
        """Get the last n data points for a sensor"""
        pass

    @abstractmethod
    def get_data_by_timeframe(
        self, data_type: str, since: float, until: float
    ) -> list[SensorData]:
        """Get sensor data within a time range"""
        pass

    @abstractmethod
    def get_sensor_id(self, sensor_name: str) -> int:
        """Get the id of a sensor by name"""
        pass

    @abstractmethod
    def add_sensor(self, sensor: SensorDescriptor) -> int:
        """Register a new sensor"""
        pass

    @abstractmethod
    def bind_sensors(self, sensor: SensorDescriptor) -> None:
        """Bind a sensor object to its database representation"""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close any open connections"""
        pass


class SQLStorage(Storage):
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

    @override
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

    @override
    def insert_data(self, data: SensorData) -> None:
        """Insert read data into the database

        Parameters
        ----------
        data : dict[str, any]
            Data read from a (one) sensor with their metadata
        """
        self.logger.debug(f"Received data in thread {threading.get_ident()}: {data}")
        self.logger.info(f"Inserting data: {data}")

        # Acquire lock for database operation
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "INSERT INTO sensors_data (sensor_id, value, unit, timestamp, data_type) VALUES (?, ?, ?, ?, ?)",
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

    @override
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
        list[SensorData]
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
                        topic=Topics.from_short_name(data[5]),
                    )
                    for data in datas
                ]

            except Exception as e:
                self.logger.error(f"Error getting data: {e}")
                return []

    @override
    def get_data_by_timeframe(
        self, data_type: str, since: float, until: float
    ) -> list[SensorData]:
        """Get the data from a specific timestamp to the current time

        Parameters
        ----------
        data_type : str
            The type of data to retrieve
        since: float
            The timestamp from which to retrieve the data
        until: float
            The timestamp to which to retrieve the data

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
                    "SELECT * FROM sensors_data WHERE data_type = ? AND timestamp >= ? AND timestamp <= ?",
                    (data_type, since, until),
                )
                datas = cursor.fetchall()
                return [
                    SensorData(
                        sensor_id=data[1],
                        value=data[2],
                        unit=data[3],
                        timestamp=data[4],
                        topic=Topics.from_short_name(data[5]),
                    )
                    for data in datas
                ]

            except Exception as e:
                self.logger.error(f"Error getting data: {e}")
                return []

    @override
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

    @override
    def add_sensor(self, sensor: SensorDescriptor) -> int:
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

    @override
    def bind_sensors(self, sensor: SensorDescriptor) -> None:
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

    @override
    def close(self):
        """Close the database connection"""
        with self.db_lock:
            if self.conn:
                self.conn.close()
                self.logger.info("Database connection closed")


class InfluxDBStorage(Storage):
    def __init__(
        self,
        url: str = Config.INFLUX_BUCKET,
        token: str = Config.INFLUX_TOKEN,
        org: str = Config.INFLUX_ORG,
        bucket: str = Config.INFLUX_BUCKET,
    ) -> None:
        """
        Initialize the InfluxDB storage client

        Parameters
        ----------
        url : str
            InfluxDB server URL
        token : str
            Authentication token
        org : str
            Organization name
        bucket : str
            Bucket name for storing sensor data
        """
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket

        # Create a client
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()

        # For sensor ID management, we need a separate mapping or table
        # Since InfluxDB doesn't handle this naturally
        self.sensor_id_mapping = {}
        self.next_sensor_id = 1
        self.id_lock = threading.Lock()
        self.db_lock = threading.Lock()

        self.logger = get_logger(__name__)

    def create_table(self) -> None:
        """Initialize storage schema - not needed for InfluxDB as it's schemaless"""
        # With InfluxDB, buckets and measurements are created on write
        # We might need to create the bucket if it doesn't exist
        with self.db_lock:
            try:
                buckets_api = self.client.buckets_api()
                existing_buckets = [b.name for b in buckets_api.find_buckets().buckets]

                if self.bucket not in existing_buckets:
                    org_id = self.client.organizations_api().find_organizations()[0].id
                    buckets_api.create_bucket(bucket_name=self.bucket, org_id=org_id)
                    self.logger.info(f"Created bucket {self.bucket}")
                else:
                    self.logger.info(f"Using existing bucket {self.bucket}")

            except Exception as e:
                self.logger.error(f"Error initializing InfluxDB: {e}")

    def insert_data(self, data: SensorData) -> None:
        """Insert a single sensor reading into InfluxDB"""
        self.logger.info(f"Inserting data: {data}")

        with self.db_lock:
            try:
                # Create a point with proper measurement, tags and fields
                point = Point("sensor_data")

                # Add tags for querying
                point = point.tag("sensor_id", str(data.sensor_id)).tag("data_type", data.data_type)

                # Add fields (actual values)
                point = point.field("value", data.value).field("unit", data.unit)

                # Set timestamp
                point = point.time(datetime.fromtimestamp(data.timestamp, tz=timezone.utc))

                # Write to InfluxDB
                self.write_api.write(bucket=self.bucket, org=self.org, record=point)

                self.logger.info(f"Successfully inserted data for sensor {data.sensor_id}")

            except Exception as e:
                self.logger.error(f"Error inserting data: {e}")

    def insert_datas(self, datas: dict[str, SensorData]) -> None:
        """Insert multiple sensor readings at once"""
        for data in datas.values():
            self.insert_data(data)

    def get_data(self, sensor_id: int, limit: int = 10) -> list[SensorData]:
        """Get the most recent data points for a specific sensor"""
        with self.db_lock:
            try:
                # Construct Flux query to get latest readings for a sensor
                query = f"""
                    from(bucket: "{self.bucket}")
                        |> range(start: -30d)
                        |> filter(fn: (r) => r._measurement == "sensor_data")
                        |> filter(fn: (r) => r.sensor_id == "{sensor_id}")
                        |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
                        |> sort(columns: ["_time"], desc: true)
                        |> limit(n: {limit})
                """

                tables = self.query_api.query(query, org=self.org)

                if not tables:
                    return []

                results = []
                for table in tables:
                    for record in table.records:
                        # Parse the record into a SensorData object
                        data_type = record.values.get("data_type", "unknown")

                        # Convert timestamp to epoch seconds for consistency
                        timestamp = record.get_time().timestamp()

                        results.append(
                            SensorData(
                                sensor_id=int(record.values.get("sensor_id")),
                                value=record.values.get("value"),
                                unit=record.values.get("unit", ""),
                                timestamp=timestamp,
                                topic=Topics.from_short_name(data_type),
                            )
                        )

                return results

            except Exception as e:
                self.logger.error(f"Error retrieving data: {e}")
                return []

    @override
    def get_data_by_timeframe(
        self, data_type: str, since: float, until: float
    ) -> list[SensorData]:
        """Get sensor data within a specific time range"""
        with self.db_lock:
            try:
                # Convert timestamps to RFC3339 format for Flux
                from_time = datetime.fromtimestamp(since, tz=timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                to_time = datetime.fromtimestamp(until, tz=timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )

                query = f"""
                    from(bucket: "{self.bucket}")
                        |> range(start: {from_time}, stop: {to_time})
                        |> filter(fn: (r) => r._measurement == "sensor_data")
                        |> filter(fn: (r) => r.data_type == "{data_type}")
                        |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
                """

                tables = self.query_api.query(query, org=self.org)

                results = []
                for table in tables:
                    for record in table.records:
                        timestamp = record.get_time().timestamp()

                        results.append(
                            SensorData(
                                sensor_id=int(record.values.get("sensor_id")),
                                value=record.values.get("value"),
                                unit=record.values.get("unit", ""),
                                timestamp=timestamp,
                                topic=Topics.from_short_name(data_type),
                            )
                        )

                return results

            except Exception as e:
                self.logger.error(f"Error retrieving data by timestamp: {e}")
                return []

    @override
    def get_sensor_id(self, sensor_name: str) -> int:
        """Get the ID of a sensor by name

        Parameters
        ----------
        sensor_name : str
            Name of the sensor

        Returns
        -------
        int
            Sensor ID, or -1 if not found
        """
        with self.db_lock:
            try:
                # First check the in-memory cache
                if sensor_name in self.sensor_id_mapping:
                    return self.sensor_id_mapping[sensor_name]

                # If not in cache, query InfluxDB
                query = f"""
                from(bucket: "{self.bucket}")
                |> range(start: -30d)
                |> filter(fn: (r) => r._measurement == "sensors")
                |> filter(fn: (r) => r.name == "{sensor_name}")
                |> limit(n: 1)
                """

                result = self.query_api.query(query=query, org=self.org)

                for table in result:
                    for record in table.records:
                        sensor_id = int(record.values.get("id", -1))
                        if sensor_id > 0:
                            # Update the cache
                            self.sensor_id_mapping[sensor_name] = sensor_id
                            return sensor_id

                return -1  # Sensor not found
            except Exception as e:
                self.logger.error(f"Error getting sensor ID: {e}")
                return -1

    @override
    def add_sensor(self, sensor: SensorDescriptor) -> int:
        """Add a new sensor to the database

        Parameters
        ----------
        sensor : SensorDataClass
            Sensor to add

        Returns
        -------
        int
            The assigned sensor ID
        """
        with self.db_lock:
            try:
                # Generate a new ID if needed (could use UUID, or your own ID generation strategy)
                new_id = max(list(self.sensor_id_mapping.values()) or [0]) + 1

                # Store sensor metadata as a point
                point = (
                    Point("sensors")
                    .tag("id", new_id)
                    .tag("name", sensor.name)
                    .field("pin", sensor.pin)
                    .field("read_interval", sensor.read_interval)
                )

                self.write_api.write(bucket=self.bucket, org=self.org, record=point)

                # Update the in-memory map
                self.sensor_id_mapping[sensor.name] = new_id

                self.logger.info(f"Added sensor {sensor.name} with ID {new_id}")
                return new_id
            except Exception as e:
                self.logger.error(f"Error adding sensor: {e}")
                return -1

    @override
    def bind_sensors(self, sensor: SensorDescriptor) -> None:
        """Bind a sensor object to its database representation

        Parameters
        ----------
        sensor : SensorDataClass
            The sensor to bind
        """
        temp_id = self.get_sensor_id(sensor.name)
        if temp_id > 0:  # Already exists in the database
            sensor.change_id(temp_id)
            self.logger.info(f"Bound sensor {sensor.name} to existing ID {sensor.sensor_id}")
        else:
            temp_id = self.add_sensor(sensor)
            sensor.change_id(temp_id)
            assert sensor.sensor_id > 0, "Error adding sensor to InfluxDB"
            self.logger.info(f"Created new sensor {sensor.name} with ID {sensor.sensor_id}")

    @override
    def close(self) -> None:
        """Close the InfluxDB client connection"""
        with self.db_lock:
            del self.write_api
            del self.query_api
            self.client.close()
            self.logger.info("InfluxDB client connection closed")
