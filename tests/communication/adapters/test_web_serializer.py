"""Tests for web serializer output."""

from dt.analytics.alerts.rules import SeverityLevel
from dt.communication.adapters import dump, load
from dt.communication.adapters.serializers.web.base import WebSerializer
from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.aggregated_reading import AggregatedReading
from dt.communication.dataclasses.alerts.alert_record import (
    AlertHistoryEvent, AlertStatus)
from dt.communication.dataclasses.analytics import (ActionResult,
                                                    ForecastResult,
                                                    ModelMetadata,
                                                    Recommendation,
                                                    RecommendedAction)
from dt.communication.dataclasses.controller.action_command import \
    ActionCommand
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.dataclasses.queries import (AnalyticsExportQuery,
                                                  ForecastHistoryQuery,
                                                  HealthHistoryQuery,
                                                  ReadingsQuery,
                                                  RecommendationHistoryQuery)
from dt.communication.topics import Topics


def test_web_dump_recommendation_converts_timestamp_and_preserves_actions() -> None:
    recommendation = Recommendation(
        plant_id=7,
        timestamp=1234.5,
        correlation_id="rec-1",
        reason="dry soil forecast",
        confidence=0.84,
        model_metadata=ModelMetadata(model_name="policy", model_version="1.0.0"),
        actions=[
            RecommendedAction(capability="irrigation", command="ON", duration_seconds=12.5),
            RecommendedAction(capability="advisory", command="inspect", duration_seconds=None),
        ],
        action_results=[
            ActionResult(action_index=0, status="accepted"),
            ActionResult(action_index=1, status="advisory_only"),
        ],
    )

    dumped = dump("web", recommendation)

    assert dumped["time"] == 1234500
    assert "timestamp" not in dumped
    assert dumped["plant_id"] == 7
    assert dumped["correlation_id"] == "rec-1"
    assert dumped["reason"] == "dry soil forecast"
    assert dumped["confidence"] == 0.84
    assert dumped["model_metadata"] == {
        "model_name": "policy",
        "model_version": "1.0.0",
    }
    assert dumped["actions"][0]["duration_seconds"] == 12.5
    assert dumped["action_results"][0]["status"] == "accepted"


def test_web_dump_alert_history_event_converts_timestamp_and_preserves_fields() -> None:
    event = AlertHistoryEvent(
        alert_key="soil-dry",
        plant_id=7,
        timestamp=1234.5,
        status=AlertStatus.ACKNOWLEDGED,
        severity=SeverityLevel.CRITICAL,
        message="soil moisture remains low",
        correlation_id="alert-1",
        acknowledged_by="operator-1",
        acknowledged_ts=1234.75,
        cleared_ts=1235.0,
    )

    dumped = dump("web", event)

    assert dumped["time"] == 1234500
    assert "timestamp" not in dumped
    assert dumped["alert_key"] == "soil-dry"
    assert dumped["status"] == AlertStatus.ACKNOWLEDGED.value
    assert dumped["severity"] == SeverityLevel.CRITICAL.value
    assert dumped["message"] == "soil moisture remains low"
    assert dumped["acknowledged_by"] == "operator-1"
    assert dumped["acknowledged_time"] == 1234750
    assert dumped["cleared_time"] == 1235000
    assert "acknowledged_ts" not in dumped
    assert "cleared_ts" not in dumped


def test_web_dump_alert_history_event_keeps_none_lifecycle_times() -> None:
    event = AlertHistoryEvent(
        alert_key="soil-dry",
        plant_id=7,
        timestamp=1234.5,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="soil moisture remains low",
        correlation_id="alert-2",
        acknowledged_ts=None,
        cleared_ts=None,
    )

    dumped = dump("web", event)

    assert dumped["acknowledged_time"] is None
    assert dumped["cleared_time"] is None
    assert "acknowledged_ts" not in dumped
    assert "cleared_ts" not in dumped


def test_web_dump_action_command_converts_event_at_to_time_and_preserves_fields() -> None:
    command = ActionCommand(
        plant_id=7,
        execution_id="exec-1",
        action_id="action-1",
        actuator_id=3,
        event_at=1234.5,
        duration=12.5,
        command="ON",
        reason="soil dry",
        correlation_id="action-1",
        source="routine",
        routine_id=9,
        status="queued",
        error_message="",
    )

    dumped = dump("web", command)

    assert dumped["time"] == 1234500
    assert "event_at" not in dumped
    assert dumped["plant_id"] == 7
    assert dumped["execution_id"] == "exec-1"
    assert dumped["action_id"] == "action-1"
    assert dumped["actuator_id"] == 3
    assert dumped["duration"] == 12.5
    assert dumped["command"] == "ON"
    assert dumped["reason"] == "soil dry"
    assert dumped["correlation_id"] == "action-1"
    assert dumped["source"] == "routine"
    assert dumped["status"] == "queued"
    assert dumped["error_message"] == ""


def test_web_dump_processed_sensor_data_uses_time_field() -> None:
    reading = ProcessedSensorData(
        plant_id=1,
        sensor_id=42,
        timestamp=1000.25,
        value=26.5,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="proc-1",
        flags={ValidationFlag.VALID: True},
        dq_score=0.99,
        imputed=False,
    )

    dumped = dump("web", reading)

    assert dumped["time"] == 1000250
    assert "timestamp" not in dumped
    assert dumped["sensor_id"] == 42


def test_web_dump_forecast_result_uses_time_field() -> None:
    forecast = ForecastResult(
        plant_id=1,
        timestamp=1000.25,
        correlation_id="forecast-1",
        metric="soil_moisture",
        horizon_seconds=3600,
        predicted_value=24.5,
        unit="%",
    )

    dumped = dump("web", forecast)

    assert dumped["time"] == 1000250
    assert "timestamp" not in dumped
    assert dumped["metric"] == "soil_moisture"


def test_web_dump_aggregated_reading_renames_bucket_to_time() -> None:
    reading = AggregatedReading(
        bucket=1000.5,
        plant_id=1,
        topic=Topics.TEMPERATURE,
        unit="Celsius",
        mean_value=25.0,
        min_value=20.0,
        max_value=30.0,
        sample_count=8,
        avg_dq_score=0.91,
        imputed_count=1,
    )

    dumped = dump("web", reading)

    assert dumped["time"] == 1000500
    assert "bucket" not in dumped
    assert dumped["topic"] == Topics.TEMPERATURE.value


def test_web_serializer_does_not_rename_bucket_in_common_helper() -> None:
    serializer = WebSerializer()

    assert serializer.move_timestamp_to_time({"bucket": 123.5}) == {"bucket": 123.5}


def test_web_serializer_helpers_handle_none_timestamp_values() -> None:
    serializer = WebSerializer()

    assert serializer.seconds_to_browser_time(None) is None
    assert serializer.move_timestamp_to_time({"timestamp": None}) == {"time": None}
    assert serializer.convert_timestamp_field({"bucket": None}, "bucket") == {"time": None}


def test_web_dump_preserves_nested_action_duration_seconds() -> None:
    recommendation = Recommendation(
        plant_id=7,
        timestamp=1234.5,
        correlation_id="rec-2",
        reason="dry soil forecast",
        confidence=0.84,
        actions=[RecommendedAction(capability="irrigation", command="ON", duration_seconds=15.0)],
    )

    dumped = dump("web", recommendation)

    assert dumped["actions"][0]["duration_seconds"] == 15.0
    assert "duration" not in dumped["actions"][0]


def test_web_dump_leaves_non_dict_payloads_unchanged() -> None:
    assert dump("web", 5) == 5


def test_web_load_readings_query_converts_browser_timestamps_to_seconds() -> None:
    query = load(
        "web",
        ReadingsQuery,
        {"since": "1000250", "until": "2000500"},
    )

    assert query.since == 1000.25
    assert query.until == 2000.5


def test_web_load_analytics_history_queries_convert_browser_timestamps_to_seconds() -> None:
    for query_type in (
        HealthHistoryQuery,
        ForecastHistoryQuery,
        RecommendationHistoryQuery,
    ):
        query = load(
            "web",
            query_type,
            {"plant_id": "1", "since": "1000250", "until": "2000500"},
        )

        assert query.since == 1000.25
        assert query.until == 2000.5


def test_web_dump_and_load_analytics_export_query_uses_browser_timestamps() -> None:
    query = load(
        "web",
        AnalyticsExportQuery,
        {"plant_id": "2", "since": "1000250", "until": "2000500", "limit": "25"},
    )

    assert query.plant_id == 2
    assert query.since == 1000.25
    assert query.until == 2000.5
    assert query.limit == 25
    assert query.effective_limit is None
    assert dump("web", query) == {
        "plant_id": 2,
        "since": 1000250,
        "until": 2000500,
        "limit": None,
    }


def test_web_dump_analytics_export_query_ignores_limit_with_time_bound() -> None:
    query = AnalyticsExportQuery(plant_id=2, since=1000.25, limit=25)

    assert query.effective_limit is None
    assert dump("web", query)["limit"] is None


def test_web_dump_analytics_export_query_keeps_limit_without_time_bounds() -> None:
    query = AnalyticsExportQuery(plant_id=2, limit=25)

    assert query.effective_limit == 25
    assert dump("web", query)["limit"] == 25
