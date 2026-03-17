from dt.communication.adapters import dump, load
from dt.communication.dataclasses.aggregated_reading import AggregatedReading
from dt.communication.topics import Topics


def test_aggregated_reading_serialization_roundtrip() -> None:
    """Round-trip AggregatedReading through the generic adapter.

    Returns
    -------
    None
        Assertions fail if Topics coercion or numeric fields regress.
    """
    payload = AggregatedReading(
        bucket=1_735_000_000.0,
        sensor_id=7,
        plant_id=2,
        topic=Topics.TEMPERATURE,
        unit="C",
        mean_value=20.0,
        min_value=18.0,
        max_value=22.0,
        sample_count=12,
        avg_dq_score=0.95,
        imputed_count=1,
        avg_raw_value=19.8,
        avg_calibrated_value=20.1,
        avg_normalized_value=0.45,
        variance_value=1.2,
        stddev_value=1.095445115,
        skewness_value=0.0,
    )

    encoded = dump("generic", payload)
    decoded = load("generic", AggregatedReading, encoded)

    assert decoded == payload
    assert decoded.topic is Topics.TEMPERATURE
