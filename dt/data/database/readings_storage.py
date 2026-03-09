from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import text

from dt.communication.adapters import dump, load
from dt.communication.dataclasses import AggregatedReading, ProcessedSensorData
from dt.communication.dataclasses.queries import ReadingsQuery
from dt.data.database.base_storage import DatabaseStorage


class ReadingsStorage(DatabaseStorage, ABC):
    """Storage capability for sensor readings persistence and queries."""

    @abstractmethod
    def ingest_reading(self, data: ProcessedSensorData) -> None:
        """Ingest a processed sensor reading into the hypertable.

        Parameters
        ----------
        data : ProcessedSensorData
            The processed sensor data to ingest.
        """
        ...

    @abstractmethod
    def ingest_readings(self, datas: list[ProcessedSensorData]) -> None:
        """Ingest multiple processed sensor readings into the hypertable.

        Parameters
        ----------
        datas : list[ProcessedSensorData]
            The list of processed sensor data to ingest.
        """
        ...

    @abstractmethod
    def query_readings(self, query: ReadingsQuery) -> list[ProcessedSensorData]:
        """Query raw readings from the hypertable.

        Parameters
        ----------
        query : ReadingsQuery
            The query parameters (sensor_id, plant_id, topic, time range, etc.).

        Returns
        -------
        list[ProcessedSensorData]
            List of raw sensor reading objects ordered by time ascending.
        """
        ...

    @abstractmethod
    def query_aggregates(self, query: ReadingsQuery) -> list[AggregatedReading]:
        """Query aggregated readings from continuous aggregates.

        Parameters
        ----------
        query : ReadingsQuery
            The query parameters including aggregation window.

        Returns
        -------
        list[AggregatedReading]
            List of aggregated reading objects ordered by bucket time.
        """
        ...


class ReadingsStore(ReadingsStorage):
    """Persistence for sensor readings and aggregates."""

    def ingest_reading(self, data: ProcessedSensorData) -> None:
        query = """
            INSERT INTO sensor_readings (
                timestamp, sensor_id, plant_id, topic, value, unit,
                correlation_id, dq_score, imputed, flags,
                raw_value, calibrated_value, normalized_value,
                calibration_profile_id, normalization_profile_id
            ) VALUES (
                to_timestamp(:timestamp), :sensor_id, :plant_id, :topic,
                :value, :unit, :correlation_id, :dq_score, :imputed,
                :flags, :raw_value, :calibrated_value,
                :normalized_value, :calibration_profile_id,
                :normalization_profile_id
            )
        """
        with self._get_connection() as conn:
            conn.execute(text(query), dump("db_row", data))
            self.logger.info(f"Ingested reading for sensor {data.sensor_id} at {data.timestamp}")

    def ingest_readings(self, datas: list[ProcessedSensorData]) -> None:
        for data in datas:
            self.ingest_reading(data)

    def query_readings(self, query: ReadingsQuery) -> list[ProcessedSensorData]:
        base_query = """
            SELECT timestamp, sensor_id, plant_id, topic, value, unit,
                   correlation_id, dq_score, imputed, flags,
                   raw_value, calibrated_value, normalized_value,
                   calibration_profile_id, normalization_profile_id
            FROM sensor_readings
            WHERE 1=1
        """
        statement, params = self._build_filter_query(base_query, query, time_col="timestamp")
        with self._get_connection() as conn:
            result = conn.execute(text(statement), params)
            readings = [load("db_row", ProcessedSensorData, row) for row in result]
            self.logger.info(f"Retrieved {len(readings)} readings")
            return readings

    def query_aggregates(self, query: ReadingsQuery) -> list[AggregatedReading]:
        window = query.window
        if window != "1h":
            raise ValueError(f"Unsupported window: {window}. Currently only '1h' is supported.")

        base_query = f"""
            SELECT bucket, sensor_id, plant_id, topic, unit,
                   avg_value, min_value, max_value, sample_count,
                   avg_dq_score, imputed_count
            FROM sensor_readings_{window}
            WHERE 1=1
        """
        statement, params = self._build_filter_query(base_query, query, time_col="bucket")
        with self._get_connection() as conn:
            result = conn.execute(text(statement), params)
            readings = [load("db_row", AggregatedReading, row) for row in result]
            self.logger.info(f"Retrieved {len(readings)} {window}-aggregated readings")
            return readings

    def _build_filter_query(
        self,
        base_query: str,
        query: ReadingsQuery,
        time_col: str,
    ) -> tuple[str, dict[str, Any]]:
        params: dict[str, Any] = {}
        statement = base_query

        if query.sensor_id is not None:
            statement += "\nAND sensor_id = :sensor_id"
            params["sensor_id"] = query.sensor_id
        if query.plant_id is not None:
            statement += "\nAND plant_id = :plant_id"
            params["plant_id"] = query.plant_id
        if query.topic is not None:
            statement += "\nAND topic = :topic"
            params["topic"] = query.topic
        if query.since is not None:
            statement += f"\nAND {time_col} >= to_timestamp(:since)"
            params["since"] = query.since
        if query.until is not None:
            statement += f"\nAND {time_col} <= to_timestamp(:until)"
            params["until"] = query.until

        statement += f"\nORDER BY {time_col} ASC"
        return statement, params
