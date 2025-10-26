import time

import requests

from dt.communication.dataclasses import (
    DBIdQuery,
    DBTimestampQuery,
    SensorDescriptor,
)
from dt.utils import Config, get_logger


class DatabaseApiClient:
    """Client for interacting with the database via Flask API endpoints.

    This class provides an abstraction layer for other components to access the
    database via HTTP requests to the Flask API, without needing to know the
    details of the API implementation.

    Parameters
    ----------
    base_url : str, optional
        The base URL of the Flask API. Defaults to the value specified in
        the application's configuration.
    """

    def __init__(self, base_url: str = Config.FLASK_DB_URL):
        self.base_url = base_url.rstrip("/")
        self.logger = get_logger(__name__)

    def bind_sensor(self, sensor: SensorDescriptor) -> int:
        """Register a sensor with the database via the API.

        Parameters
        ----------
        sensor : SensorDescriptor
            The sensor descriptor object to register.

        Returns
        -------
        int
            The ID assigned to the sensor by the database, or -1 on error.
        """
        try:
            response = requests.post(
                f"{self.base_url}/bind_sensor",
                json=sensor.to_json(),
                headers={"Content-Type": "application/json"},
                timeout=5,
            )

            if response.status_code == 200:
                return response.json().get("sensor_id", -1)
            self.logger.error(f"Error registering sensor: {response.text}")
            return -1
        except requests.Timeout:
            self.logger.error("Timeout occurred while trying to bind sensor.")
            return -1
        except requests.RequestException as e:
            self.logger.error(f"Error in bind_sensor API call: {e}")
            return -1

    def list_sensors(self) -> list[SensorDescriptor]:
        """Return all sensors registered in the database."""

        try:
            response = requests.get(
                f"{self.base_url}/sensors",
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            if response.status_code != 200:
                self.logger.error(f"Error retrieving sensors: {response.text}")
                return []
            payload = response.json()
            sensors: list[SensorDescriptor] = []
            for item in payload:
                try:
                    sensors.append(SensorDescriptor.from_json(item))
                except Exception as exc:
                    self.logger.error(f"Failed to parse sensor descriptor {item}: {exc}")
            return sensors
        except requests.Timeout:
            self.logger.error("Timeout occurred while listing sensors.")
            return []
        except requests.RequestException as exc:
            self.logger.error(f"Error in list_sensors API call: {exc}")
            return []

    def get_data_by_timeframe(self, time_frame: DBTimestampQuery) -> list[dict]:
        """Get sensor data within a specific time range.

        Parameters
        ----------
        time_frame : DBTimestampQuery
            A query object specifying the data type and the time range (since
            and until timestamps).

        Returns
        -------
        List[Dict]
            A list of sensor data dictionaries, or an empty list on error.
        """

        try:
            response = requests.post(
                f"{self.base_url}/data/timestamp",
                json=time_frame.to_json(),
                headers={"Content-Type": "application/json"},
                timeout=5,
            )

            if response.status_code == 200:
                return response.json()
            self.logger.error(f"Error fetching data: {response.text}")
            return []
        except requests.Timeout:
            self.logger.error("Timeout occurred while trying to get data by timeframe.")
            return []
        except requests.RequestException as e:
            self.logger.error(f"Error in get_data_by_timeframe API call: {e}")
            return []

    def get_recent_data(self, sensor_id: int, limit: int = 10) -> list[dict]:
        """Get the most recent data points for a specific sensor.

        Parameters
        ----------
        sensor_id : int
            The ID of the sensor.
        limit : int, optional
            The maximum number of records to return, by default 10.

        Returns
        -------
        List[Dict]
            A list of sensor data dictionaries, or an empty list on error.
        """
        query = DBIdQuery(sensor_id=sensor_id, limit=limit)
        try:
            response = requests.post(
                f"{self.base_url}/data/id",
                json=query.to_json(),
                headers={"Content-Type": "application/json"},
                timeout=5,
            )

            if response.status_code == 200:
                return response.json()
            self.logger.error(f"Error fetching sensor data: {response.text}")
            return []

        except requests.Timeout:
            self.logger.error("Timeout occurred while trying to get recent data.")
            return []
        except requests.RequestException as e:
            print(f"Error in get_recent_data API call: {e}")
            self.logger.error(f"Error in get_recent_data API call: {e}")
            return []

    def get_data_for_last(self, data_type: str, hours: int = 24) -> list[dict]:
        """Fetch data for a specified number of hours leading up to the present.

        Parameters
        ----------
        data_type : str
            The type of data to retrieve (e.g., "temperature").
        hours : int, optional
            The number of hours of data to retrieve, by default 24.

        Returns
        -------
        List[Dict]
            A list of sensor data dictionaries.
        """
        end_time = time.time()
        start_time = end_time - (hours * 3600)

        timeframe = DBTimestampQuery(
            data_type=data_type,
            since=start_time,
            until=end_time,
        )

        return self.get_data_by_timeframe(timeframe)

    def get_latest_value(self, data_type: str) -> dict | None:
        """Get the most recent value for a specific data type.

        This method retrieves data from the last hour and returns the most
        recent data point.

        Parameters
        ----------
        data_type : str
            The type of data to retrieve (e.g., "temperature").

        Returns
        -------
        Optional[Dict]
            The most recent sensor data dictionary, or ``None`` if no data
            exists or an error occurs.
        """
        # Get a small window of recent data and take the most recent
        try:
            # Get data from the last hour

            start_time = time.time() - 3600
            end_time = time.time()
            timeframe = DBTimestampQuery(
                data_type=data_type,
                since=start_time,
                until=end_time,
            )
            data = self.get_data_by_timeframe(timeframe)

            if not data:
                return None

            # Sort by timestamp and return the most recent
            return max(data, key=lambda x: x.get("timestamp", 0))

        except Exception as e:
            self.logger.error(f"Error in get_latest_value API call: {e}")
            return None
