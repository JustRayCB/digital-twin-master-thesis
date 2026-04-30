from dataclasses import dataclass

from dt.communication.topics import Topics


@dataclass
class AggregatedReading:
    """Represents a plant/topic hourly aggregate over a time window.

    This dataclass holds statistics computed by TimescaleDB continuous aggregates
    for a plant/topic series and time bucket.

    Attributes
    ----------
    bucket : float
        The start timestamp of the aggregation window (Unix timestamp).
    plant_id : int
        The ID of the plant.
    topic: str
        The type of data (e.g., "temperature", "humidity").
    unit : str
        The unit of measurement (e.g., "°C", "%").
    mean_value : float
        The arithmetic mean over the window.
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
    avg_raw_value : float | None
        The average raw sensor reading over the window, when available.
    avg_calibrated_value : float | None
        The average calibrated sensor reading over the window, when available.
    avg_normalized_value : float | None
        The average normalized sensor reading over the window, when available.
    variance_value : float | None
        The sample variance over the window, when defined.
    stddev_value : float | None
        The sample standard deviation over the window, when defined.
    skewness_value : float | None
        The sample skewness over the window, when defined.
    kurtosis_value : float | None
        The sample kurtosis over the window, when defined.
    """

    bucket: float
    plant_id: int
    topic: Topics
    unit: str
    mean_value: float
    min_value: float
    max_value: float
    sample_count: int
    avg_dq_score: float
    imputed_count: int
    avg_raw_value: float | None = None
    avg_calibrated_value: float | None = None
    avg_normalized_value: float | None = None
    variance_value: float | None = None
    stddev_value: float | None = None
    skewness_value: float | None = None
    kurtosis_value: float | None = None
