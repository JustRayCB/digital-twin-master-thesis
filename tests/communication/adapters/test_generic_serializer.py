"""Tests for GenericSerializer."""

from dt.communication.adapters.serializers.generic.base import \
    GenericSerializer
from dt.communication.dataclasses.analytics import (ActionResult, ForecastResult,
                                                    HealthAssessment, Recommendation,
                                                    RecommendedAction)
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics


def test_generic_serializer_dump_returns_dict(raw_sensor_data):
    serializer = GenericSerializer()
    dumped = serializer.dump(raw_sensor_data)
    assert dumped["topic"] == Topics.TEMPERATURE.value
    assert type(dumped["topic"]) is str
    assert dumped["sensor_id"] == 42


def test_generic_serializer_load_builds_target_dataclass():
    serializer = GenericSerializer()
    data = {
        "plant_id": 1,
        "sensor_id": 42,
        "timestamp": 1234567890.5,
        "value": 25.3,
        "unit": "Celsius",
        "topic": Topics.TEMPERATURE.value,
        "correlation_id": "test-123",
    }
    loaded = serializer.load(RawSensorData, data)
    assert isinstance(loaded, RawSensorData)
    assert loaded.topic == Topics.TEMPERATURE


def test_generic_serializer_loads_analytics_contracts() -> None:
    serializer = GenericSerializer()

    health = serializer.load(
        HealthAssessment,
        {
            "plant_id": 3,
            "timestamp": 1000.0,
            "correlation_id": "h-1",
            "state": "healthy",
            "score": 0.95,
            "summary": "stable",
        },
    )
    forecast = serializer.load(
        ForecastResult,
        {
            "plant_id": 3,
            "timestamp": 1001.0,
            "correlation_id": "f-1",
            "metric": "soil_moisture",
            "horizon_seconds": 300,
            "predicted_value": 44.0,
            "unit": "%",
        },
    )
    recommendation = serializer.load(
        Recommendation,
        {
            "plant_id": 3,
            "timestamp": 1002.0,
            "correlation_id": "r-1",
            "confidence": 0.9,
            "reason": "forecast drop",
            "actions": [
                {
                    "capability": "irrigation",
                    "command": "ON",
                    "duration_seconds": 5.0,
                }
            ],
            "action_results": [
                {
                    "action_index": 0,
                    "status": "accepted",
                }
            ],
        },
    )

    assert isinstance(health, HealthAssessment)
    assert isinstance(forecast, ForecastResult)
    assert isinstance(recommendation, Recommendation)
    assert recommendation.actions == [
        RecommendedAction(capability="irrigation", command="ON", duration_seconds=5.0)
    ]
    assert recommendation.action_results == [ActionResult(action_index=0, status="accepted")]
