import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from typing_extensions import override

from dt.communication import Topics
from dt.communication.dataclasses import RawSensorData, SensorDescriptor
from dt.utils import Config, get_logger


class Storage(ABC):
    """Abstract base class for storage implementations"""

    @abstractmethod
    def create_table(self) -> None:
        """Initialize storage schema"""
        pass

    @abstractmethod
    def insert_data(self, data: RawSensorData) -> None:
        """Insert a single sensor data reading.

        Parameters
        ----------
        data : SensorData
            The sensor data to be inserted.
        """
        pass

    @abstractmethod
    def insert_datas(self, datas: dict[str, RawSensorData]) -> None:
        """Insert multiple sensor data readings.

        Parameters
        ----------
        datas : dict[str, SensorData]
            A dictionary of sensor data objects to be inserted.
        """
        pass

    @abstractmethod
    def get_data(self, sensor_id: int, limit: int = 10) -> list[RawSensorData]:
        """Get the last N data points for a specific sensor.

        Parameters
        ----------
        sensor_id : int
            The ID of the sensor to retrieve data for.
        limit : int, optional
            The maximum number of data points to return, by default 10.

        Returns
        -------
        list[SensorData]
            A list of sensor data objects.
        """
        pass

    @abstractmethod
    def get_data_by_timeframe(
        self, data_type: str, since: float, until: float
    ) -> list[RawSensorData]:
        """Get sensor data of a specific type within a given time range.

        Parameters
        ----------
        data_type : str
            The type of data to retrieve (e.g., "temperature").
        since : float
            The start of the time range as a Unix timestamp.
        until : float
            The end of the time range as a Unix timestamp.

        Returns
        -------
        list[SensorData]
            A list of sensor data objects.
        """
        pass

    @abstractmethod
    def get_sensor_id(self, sensor_name: str) -> int:
        """Get the ID of a sensor by its name.

        Parameters
        ----------
        sensor_name : str
            The name of the sensor.

        Returns
        -------
        int
            The ID of the sensor, or -1 if not found.
        """
        pass

    @abstractmethod
    def add_sensor(self, sensor: SensorDescriptor) -> int:
        """Register a new sensor and return its assigned ID.

        Parameters
        ----------
        sensor : SensorDescriptor
            The descriptor of the sensor to be added.

        Returns
        -------
        int
            The assigned ID of the newly added sensor, or -1 on error.
        """
        pass

    @abstractmethod
    def bind_sensors(self, sensor: SensorDescriptor) -> None:
        """Bind a sensor object to its database representation.

        This method checks if a sensor with the given name already exists.
        If it does, it updates the sensor object with the existing ID.
        If not, it adds the sensor to the database and updates it with the
        newly assigned ID.

        Parameters
        ----------
        sensor : SensorDescriptor
            The sensor to be bound.
        """
        pass

    @abstractmethod
    def list_sensors(self) -> list[SensorDescriptor]:
        """Return all registered sensors."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close any open connections"""
        pass


class InfluxDBStorage(Storage):
    """An InfluxDB-based implementation of the Storage interface.

    This class uses an InfluxDB instance to store and retrieve time-series
    sensor data. It uses an in-memory dictionary to manage sensor names
    and their corresponding IDs, as InfluxDB is not designed for relational
    metadata management.

    Parameters
    ----------
    url : str, optional
        The URL of the InfluxDB server.
    token : str, optional
        The authentication token for InfluxDB.
    org : str, optional
        The organization to use in InfluxDB.
    bucket : str, optional
        The bucket to store sensor data in.
    """

    def __init__(
        self,
        url: str = Config.INFLUX_URL,
        token: str = Config.INFLUX_TOKEN,
        org: str = Config.INFLUX_ORG,
        bucket: str = Config.INFLUX_BUCKET,
    ) -> None:
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
        self.db_lock = threading.Lock()

        self.logger = get_logger(__name__)
        self.create_table()

    @override
    def create_table(self) -> None:
        """Initialize the storage schema.

        For InfluxDB, this means ensuring that the target bucket exists.
        If it does not, it will be created.
        """
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

    @override
    def insert_data(self, data: RawSensorData) -> None:
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

    @override
    def insert_datas(self, datas: dict[str, RawSensorData]) -> None:
        for data in datas.values():
            self.insert_data(data)

    @override
    def get_data(self, sensor_id: int, limit: int = 10) -> list[RawSensorData]:
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
                            RawSensorData(
                                plant_id=int(record.values.get("plant_id", -1)),
                                sensor_id=int(record.values.get("sensor_id", -1)),
                                value=record.values.get("value", -1),
                                unit=record.values.get("unit", "None"),
                                timestamp=timestamp,
                                topic=Topics.from_short_name(data_type),
                                correlation_id=record.values.get("correlation_id", "abc-123"),
                            )
                        )

                return results

            except Exception as e:
                self.logger.error(f"Error retrieving data: {e}")
                return []

    @override
    def get_data_by_timeframe(
        self, data_type: str, since: float, until: float
    ) -> list[RawSensorData]:
        with self.db_lock:
            try:
                # Convert timestamps to RFC3339 format for Flux
                from_time = datetime.fromtimestamp(since, tz=timezone.utc).isoformat()
                to_time = datetime.fromtimestamp(until, tz=timezone.utc).isoformat()

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
                            RawSensorData(
                                plant_id=int(record.values.get("plant_id", -1)),
                                sensor_id=int(record.values.get("sensor_id", -1)),
                                value=record.values.get("value", -1),
                                unit=record.values.get("unit", "None"),
                                timestamp=timestamp,
                                topic=Topics.from_short_name(data_type),
                                correlation_id=record.values.get("correlation_id", "abc-123"),
                            )
                        )

                return results

            except Exception as e:
                self.logger.error(f"Error retrieving data by timestamp: {e}")
                return []

    @override
    def get_sensor_id(self, sensor_name: str) -> int:
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
    def list_sensors(self) -> list[SensorDescriptor]:
        raise NotImplementedError("Listing sensors is not implemented for InfluxDBStorage.")

    @override
    def close(self) -> None:
        """Close the InfluxDB client connection"""
        with self.db_lock:
            del self.write_api
            del self.query_api
            self.client.close()
            self.logger.info("InfluxDB client connection closed")
