import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import requests

from dt.utils import Config, SensorData, SensorDescriptor, get_logger
from dt.utils.dataclasses import DBIdQuery, DBTimestampQuery


class DatabaseApiClient:
    """
    Client for interacting with the database through the Flask API endpoints.

    This class provides an abstraction layer for other components to access the
    database via HTTP requests to the Flask API, without needing to know the
    details of the API implementation.
    """

    def __init__(self, base_url: str = Config.FLASK_DB_URL):
        """
        Initialize the API client.

        Parameters
        ----------
        base_url : str, optional
            The base URL of the Flask API, by default "http://localhost:5001"
        """
        self.base_url = base_url.rstrip("/")
        self.logger = get_logger(__name__)

    def bind_sensor(self, sensor: SensorDescriptor) -> int:
        """
        Register a sensor via the API.

        Parameters
        ----------
        sensor : SensorDataClass
            The sensor to register

        Returns
        -------
        int
            The ID assigned to the sensor, or -1 on error
        """
        try:
            response = requests.post(
                f"{self.base_url}/bind_sensor",
                json=sensor.to_json(),
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                return response.json().get("sensor_id", -1)
            else:
                self.logger.error(f"Error registering sensor: {response.text}")
                return -1

        except Exception as e:
            self.logger.error(f"Error in bind_sensor API call: {e}")
            return -1

    def get_data_by_timeframe(self, time_frame: DBTimestampQuery) -> List[Dict]:
        """
        Get sensor data within a specific time range.

        Parameters
        ----------
        time_frame : DBTimestampQuery
            The time frame for the data query:
                - data_type: str
                - from_timestamp: float
                - to_timestamp: float

        Returns
        -------
        List[Dict]
            List of sensor data dictionaries
        """

        try:
            response = requests.post(
                f"{self.base_url}/data/timestamp",
                json=time_frame.to_json(),
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Error fetching data: {response.text}")
                return []

        except Exception as e:
            self.logger.error(f"Error in get_data_by_timeframe API call: {e}")
            return []

    def get_recent_data(self, sensor_id: int, limit: int = 10) -> List[Dict]:
        """
        Get the most recent data for a specific sensor.

        Parameters
        ----------
        sensor_id : int
            The ID of the sensor
        limit : int, optional
            Maximum number of records to return, by default 10

        Returns
        -------
        List[Dict]
            List of sensor data dictionaries
        """
        query = DBIdQuery(sensor_id=sensor_id, limit=limit)
        try:
            response = requests.post(
                f"{self.base_url}/data/id",
                json=query.to_json(),
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Error fetching sensor data: {response.text}")
                return []

        except Exception as e:
            print(f"Error in get_recent_data API call: {e}")
            self.logger.error(f"Error in get_recent_data API call: {e}")
            return []

    def get_data_for_last(self, data_type: str, hours: int = 24) -> List[Dict]:
        """
        Convenience method to get data for a time period leading up to now.

        Parameters
        ----------
        data_type : str
            The type of data to retrieve
        hours : int, optional
            How many hours of data to retrieve, by default 24

        Returns
        -------
        List[Dict]
            List of sensor data dictionaries
        """
        end_time = time.time()
        start_time = end_time - (hours * 3600)

        timeframe = DBTimestampQuery(
            data_type=data_type,
            since=start_time,
            until=end_time,
        )

        return self.get_data_by_timeframe(timeframe)

    def get_latest_value(self, data_type: str) -> Optional[Dict]:
        """
        Get the most recent value for a specific data type.

        Parameters
        ----------
        data_type : str
            The type of data to retrieve

        Returns
        -------
        Optional[Dict]
            The most recent sensor data dictionary, or None if no data exists
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
