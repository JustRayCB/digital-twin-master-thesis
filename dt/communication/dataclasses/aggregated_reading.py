from dataclasses import dataclass

from dt.communication.topics import Topics


@dataclass
class AggregatedReading:
    """Represents an aggregated sensor reading over a time window.

    This dataclass holds statistics computed by TimescaleDB continuous aggregates
    for a specific sensor, data type, and time bucket.

    Attributes
    ----------
    bucket : float
        The start timestamp of the aggregation window (Unix timestamp).
    sensor_id : int
        The ID of the sensor.
    plant_id : int
        The ID of the plant.
    topic: str
        The type of data (e.g., "temperature", "humidity").
    unit : str
        The unit of measurement (e.g., "°C", "%").
    avg_value : float
        The average value over the window.
    min_value : float
        The minimum value over the window.
    max_value : float
        The maximum value over the window.
    sample_count : int
        The number of samples in the window.
    avg_dq_score : float
        The average data quality score over the window.
    imputed_count : int
        The number of imputed samples in the window.
    """

    bucket: float
    sensor_id: int
    plant_id: int
    topic: Topics
    unit: str
    avg_value: float
    min_value: float
    max_value: float
    sample_count: int
    avg_dq_score: float
    imputed_count: int
