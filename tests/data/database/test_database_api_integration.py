"""Integration tests for the database service REST API."""

import pytest
from sqlalchemy import text

from dt.analytics.alerts.rules import SeverityLevel
from dt.communication.adapters import dump, load
from dt.communication.dataclasses import (
    ActionResult,
    CameraSnapshot,
    ForecastResult,
    HealthAssessment,
    HealthState,
    Recommendation,
    RecommendedAction,
    ProcessedSensorData,
    ModelMetadata,
    SensorDescriptor,
)
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertHistoryEvent,
    AlertStatus,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.dataclasses.queries import (
    ActiveAlertsQuery,
    AlertHistoryQuery,
    CameraSnapshotQuery,
    ForecastHistoryQuery,
    HealthHistoryQuery,
    RecommendationHistoryQuery,
    ReadingsQuery,
)
from dt.communication.topics import Topics
from dt.data.database.analytics_storage import AnalyticsStore

pytestmark = [pytest.mark.requires_timescale]


def load_alert_event(payload: dict) -> AlertHistoryEvent:
    """Deserialize alert payloads into alert event types.

    Parameters
    ----------
    payload : dict
        Serialized alert payload returned by the database API.

    Returns
    -------
    AlertHistoryEvent
        Structured alert event instance.
    """
    if "reading" in payload:
        return load("generic", SensorAlertEvent, payload)
    if "metadata" in payload:
        return load("generic", ExternalAlertEvent, payload)
    return load("generic", AlertHistoryEvent, payload)


def test_list_sensors_returns_registered_sensors(client, sample_sensor) -> None:
    """List sensors returns relational sensor metadata.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor.

    Returns
    -------
    None
        The assertions raise if /sensors output regresses.
    """
    response = client.get("/sensors")

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    sensors = [load("generic", SensorDescriptor, item) for item in payload]

    assert any(sensor.id == sample_sensor.id for sensor in sensors)


def test_bind_sensor_persists_to_database(
    client, sample_plant_id: int, metadata_store
) -> None:
    """Bind sensor endpoint registers a sensor and returns the assigned ID.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    sample_plant_id : int
        Plant identifier to bind the sensor to.
    metadata_store : MetadataStore
        Store used to validate persistence.

    Returns
    -------
    None
        The assertions raise if /bind_sensor regresses.
    """
    sensor = SensorDescriptor(
        id=0,
        plant_id=sample_plant_id,
        name="new_sensor",
        pin=5,
        read_interval=120,
    )
    response = client.post("/bind_sensor", json=dump("generic", sensor))

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    sensor_id = payload["sensor_id"]
    assert sensor_id > 0

    sensors = metadata_store.list_sensors()
    assert any(
        sensor.id == sensor_id and sensor.name == "new_sensor" for sensor in sensors
    )


def test_bind_sensor_rejects_invalid_json(client) -> None:
    """Bind sensor endpoint rejects invalid JSON payloads.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.

    Returns
    -------
    None
        The assertions raise if /bind_sensor error handling regresses.
    """
    response = client.post(
        "/bind_sensor", data="not json", content_type="application/json"
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "error" in payload


def test_get_readings_returns_raw_data(client, readings_store, sample_sensor) -> None:
    """Readings endpoint returns persisted readings for a sensor.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    readings_store : ReadingsStore
        Store used to seed readings.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor.

    Returns
    -------
    None
        The assertions raise if /readings raw query regresses.
    """
    readings_store.ingest_reading(
        ProcessedSensorData(
            plant_id=sample_sensor.plant_id,
            sensor_id=sample_sensor.id,
            timestamp=1234567890.0,
            value=25.5,
            unit="°C",
            topic=Topics.TEMPERATURE,
            correlation_id="test-123",
            flags={},
            dq_score=0.98,
            imputed=False,
        )
    )

    query = ReadingsQuery(window="raw", sensor_id=sample_sensor.id)
    response = client.get("/readings", query_string=dump("generic", query))

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)

    readings = [load("generic", ProcessedSensorData, item) for item in payload]
    assert readings
    assert any(reading.correlation_id == "test-123" for reading in readings)


def test_get_readings_returns_1h_aggregate_stats(
    client, readings_store, sample_sensor
) -> None:
    """Readings endpoint returns hourly aggregate statistics for a sensor."""
    base_timestamp = 1_735_689_600.0
    for index in range(6):
        readings_store.ingest_reading(
            ProcessedSensorData(
                plant_id=sample_sensor.plant_id,
                sensor_id=sample_sensor.id,
                timestamp=base_timestamp + index * 600,
                value=20.0 + index,
                unit="°C",
                topic=Topics.TEMPERATURE,
                correlation_id=f"agg-{index}",
                flags={},
                dq_score=1.0,
                imputed=False,
            )
        )

    with readings_store.engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as conn:
        conn.execute(
            text("CALL refresh_continuous_aggregate('sensor_readings_1h', NULL, NULL);")
        )

    query = ReadingsQuery(
        window="1h",
        since=base_timestamp - 60,
        until=base_timestamp + 7200,
    )
    response = client.get("/readings", query_string=dump("generic", query))

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["mean_value"] == pytest.approx(22.5)
    assert payload[0]["variance_value"] == pytest.approx(3.5)
    assert payload[0]["stddev_value"] == pytest.approx(3.5**0.5)
    assert payload[0]["skewness_value"] == pytest.approx(0.0, abs=1e-12)


def test_get_readings_1h_combines_same_topic_across_sensors(
    client, readings_store, sample_sensor, metadata_store
) -> None:
    """1h aggregate queries combine same-topic hourly series across sensors."""
    second_sensor = SensorDescriptor(
        id=0,
        plant_id=sample_sensor.plant_id,
        name="test_sensor_2",
        pin=8,
        read_interval=60,
    )
    second_sensor.id = metadata_store.register_sensor(second_sensor)

    base_timestamp = 1_735_689_600.0
    for sensor_id, value in ((sample_sensor.id, 10.0), (second_sensor.id, 30.0)):
        readings_store.ingest_reading(
            ProcessedSensorData(
                plant_id=sample_sensor.plant_id,
                sensor_id=sensor_id,
                timestamp=base_timestamp + sensor_id,
                value=value,
                unit="°C",
                topic=Topics.TEMPERATURE,
                correlation_id=f"agg-combined-{sensor_id}",
                flags={},
                dq_score=1.0,
                imputed=False,
            )
        )

    with readings_store.engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as conn:
        conn.execute(
            text("CALL refresh_continuous_aggregate('sensor_readings_1h', NULL, NULL);")
        )

    query = ReadingsQuery(
        window="1h",
        plant_id=sample_sensor.plant_id,
        topic=Topics.TEMPERATURE.value,
        since=base_timestamp - 60,
        until=base_timestamp + 3600,
    )
    response = client.get("/readings", query_string=dump("generic", query))

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["sample_count"] == 2
    assert payload[0]["mean_value"] == pytest.approx(20.0)
    assert payload[0]["min_value"] == pytest.approx(10.0)
    assert payload[0]["max_value"] == pytest.approx(30.0)


def test_get_readings_rejects_invalid_query_params(client) -> None:
    """Readings endpoint rejects invalid query parameters.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.

    Returns
    -------
    None
        The assertions raise if /readings parameter validation regresses.
    """
    response = client.get("/readings", query_string={"since": "not-a-float"})

    assert response.status_code == 400
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "error" in payload


def test_get_latest_camera_snapshot_returns_404_when_absent(client) -> None:
    """Latest snapshot endpoint returns 404 when no snapshot is available."""
    response = client.get("/camera/snapshots/latest", query_string={"plant_id": 1})

    assert response.status_code == 404
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "error" in payload


def test_get_latest_camera_snapshot_returns_camera_payload(
    client, snapshot_store, sample_sensor: SensorDescriptor
) -> None:
    """Latest snapshot endpoint returns persisted camera payload in API shape."""
    snapshot = CameraSnapshot(
        plant_id=sample_sensor.plant_id,
        sensor_id=sample_sensor.id,
        timestamp=1234567890.0,
        topic=Topics.CAMERA_IMAGE_TOP,
        correlation_id="camera-123",
        mime_type="image/jpeg",
        image="AQI=",
        width=640,
        height=480,
    )
    snapshot_store.ingest_camera_snapshot(snapshot)

    response = client.get(
        "/camera/snapshots/latest",
        query_string={"plant_id": sample_sensor.plant_id},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert load("generic", CameraSnapshot, payload) == snapshot


def test_get_latest_camera_snapshot_filters_by_topic(
    client, snapshot_store, sample_sensor: SensorDescriptor
) -> None:
    """Latest snapshot endpoint returns the requested camera topic."""
    top_snapshot = CameraSnapshot(
        plant_id=sample_sensor.plant_id,
        sensor_id=sample_sensor.id,
        timestamp=1234567890.0,
        topic=Topics.CAMERA_IMAGE_TOP,
        correlation_id="camera-top",
        mime_type="image/jpeg",
        image="AQI=",
        width=640,
        height=480,
    )
    side_snapshot = CameraSnapshot(
        plant_id=sample_sensor.plant_id,
        sensor_id=sample_sensor.id,
        timestamp=1234567990.0,
        topic=Topics.CAMERA_IMAGE_SIDE,
        correlation_id="camera-side",
        mime_type="image/jpeg",
        image="AQM=",
        width=480,
        height=640,
    )
    snapshot_store.ingest_camera_snapshot(top_snapshot)
    snapshot_store.ingest_camera_snapshot(side_snapshot)

    response = client.get(
        "/camera/snapshots/latest",
        query_string={
            "plant_id": sample_sensor.plant_id,
            "topic": Topics.CAMERA_IMAGE_TOP.value,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert load("generic", CameraSnapshot, payload) == top_snapshot


def test_query_camera_snapshots_returns_interval_filtered_payloads(
    client, snapshot_store, sample_sensor: SensorDescriptor
) -> None:
    """Camera snapshots endpoint returns snapshots within the requested interval."""
    for timestamp, correlation_id in (
        (1_735_689_600.0, "camera-early"),
        (1_735_689_700.0, "camera-middle"),
        (1_735_689_800.0, "camera-late"),
    ):
        snapshot_store.ingest_camera_snapshot(
            CameraSnapshot(
                plant_id=sample_sensor.plant_id,
                sensor_id=sample_sensor.id,
                timestamp=timestamp,
                topic=Topics.CAMERA_IMAGE_TOP,
                correlation_id=correlation_id,
                mime_type="image/jpeg",
                image="AQI=",
                width=640,
                height=480,
            )
        )

    response = client.get(
        "/camera/snapshots",
        query_string=dump(
            "generic",
            CameraSnapshotQuery(
                plant_id=sample_sensor.plant_id,
                since=1_735_689_650.0,
                until=1_735_689_750.0,
            ),
        ),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    snapshots = [load("generic", CameraSnapshot, item) for item in payload]
    assert [snapshot.correlation_id for snapshot in snapshots] == ["camera-middle"]


def test_get_analytics_health_history_returns_persisted_assessments(
    client, db_engine, metadata_store
) -> None:
    """Analytics health history returns persisted health assessments."""
    plant_id = metadata_store.upsert_plant(name="Health History Plant")
    analytics_store = AnalyticsStore(engine=db_engine)
    first_assessment = HealthAssessment(
        plant_id=plant_id,
        timestamp=1_735_689_500.0,
        correlation_id="health-corr-0",
        state=HealthState.HEALTHY,
        score=0.87,
        summary="Plant is stable",
        confidence=0.98,
        model_metadata=ModelMetadata(model_name="health-baseline", model_version="1.0"),
    )
    assessment = HealthAssessment(
        plant_id=plant_id,
        timestamp=1_735_689_600.0,
        correlation_id="health-corr-1",
        state=HealthState.CRITICAL,
        score=0.12,
        summary="Plant is dry and stressed",
        confidence=0.91,
        model_metadata=ModelMetadata(model_name="health-baseline", model_version="1.0"),
    )

    analytics_store.log_health_assessment(first_assessment)
    
    analytics_store.log_health_assessment(assessment)

    response = client.get(
        "/analytics/health",
        query_string=dump(
            "generic",
            HealthHistoryQuery(
                plant_id=plant_id,
                since=1_735_689_550.0,
                until=1_735_689_650.0,
                limit=1,
                correlation_id="health-corr-1",
            ),
        ),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert [load("generic", HealthAssessment, item) for item in payload] == [assessment]


def test_get_analytics_health_history_returns_all_rows_without_limit(
    client, db_engine, metadata_store
) -> None:
    """Analytics health history should not truncate when limit is omitted."""
    plant_id = metadata_store.upsert_plant(name="Unbounded Health History Plant")
    analytics_store = AnalyticsStore(engine=db_engine)

    assessments = [
        HealthAssessment(
            plant_id=plant_id,
            timestamp=1_735_689_600.0 + index,
            correlation_id=f"health-corr-{index}",
            state=HealthState.CRITICAL if index % 2 else HealthState.HEALTHY,
            score=0.12 if index % 2 else 0.87,
            summary=f"Assessment {index}",
            confidence=0.91,
            model_metadata=ModelMetadata(model_name="health-baseline", model_version="1.0"),
        )
        for index in range(101)
    ]

    for assessment in assessments:
        analytics_store.log_health_assessment(assessment)

    response = client.get(
        "/analytics/health",
        query_string=dump("generic", HealthHistoryQuery(plant_id=plant_id)),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert len(payload) == 101
    assert [load("generic", HealthAssessment, item) for item in payload] == assessments[::-1]


def test_get_analytics_forecast_history_returns_persisted_forecasts(
    client, db_engine, metadata_store
) -> None:
    """Analytics forecast history returns persisted forecast results."""
    plant_id = metadata_store.upsert_plant(name="Forecast History Plant")
    analytics_store = AnalyticsStore(engine=db_engine)
    first_forecast = ForecastResult(
        plant_id=plant_id,
        timestamp=1_735_689_650.0,
        correlation_id="forecast-corr-0",
        metric="temperature",
        horizon_seconds=1800,
        predicted_value=23.0,
        unit="°C",
        model_metadata=ModelMetadata(model_name="temperature-forecaster", model_version="1.0"),
        features_used=["temperature.last"],
        inference_metadata={"confidence": 0.51},
    )
    forecast = ForecastResult(
        plant_id=plant_id,
        timestamp=1_735_689_700.0,
        correlation_id="forecast-corr-1",
        metric="soil_moisture",
        horizon_seconds=3600,
        predicted_value=24.5,
        unit="%",
        model_metadata=ModelMetadata(model_name="moisture-forecaster", model_version="2.0"),
        features_used=["soil_moisture.last", "context.soil_moisture_mean_24h"],
        inference_metadata={"confidence": 0.73},
    )

    analytics_store.log_forecast_result(first_forecast)
    analytics_store.log_forecast_result(forecast)

    response = client.get(
        "/analytics/forecasts",
        query_string=dump(
            "generic",
            ForecastHistoryQuery(
                plant_id=plant_id,
                metric="soil_moisture",
                horizon_seconds=3600,
                since=1_735_689_680.0,
                until=1_735_689_750.0,
                limit=1,
                correlation_id="forecast-corr-1",
            ),
        ),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert [load("generic", ForecastResult, item) for item in payload] == [forecast]


def test_get_analytics_recommendation_history_returns_unified_recommendations(
    client, db_engine, metadata_store
) -> None:
    """Analytics recommendation history returns unified recommendation objects."""
    plant_id = metadata_store.upsert_plant(name="Recommendation History Plant")
    analytics_store = AnalyticsStore(engine=db_engine)
    first_recommendation = Recommendation(
        plant_id=plant_id,
        timestamp=1_735_689_750.0,
        correlation_id="lifecycle-corr-0",
        confidence=0.94,
        reason="Dry forecast and high confidence",
        actions=[
            RecommendedAction(
                capability="irrigation",
                command="ON",
                duration_seconds=5.0,
            )
        ],
        model_metadata=ModelMetadata(model_name="policy-engine", model_version="1.0"),
        action_results=[
            ActionResult(action_index=0, status="accepted")
        ],
    )
    recommendation = Recommendation(
        plant_id=plant_id,
        timestamp=1_735_689_800.0,
        correlation_id="lifecycle-corr-1",
        confidence=0.61,
        reason="Health is stressed but irrigation guard is not met",
        actions=[RecommendedAction(capability="advisory", command="inspect_plant")],
        model_metadata=ModelMetadata(model_name="policy-engine", model_version="1.0"),
        action_results=[
            ActionResult(action_index=0, status="advisory_only")
        ],
    )

    analytics_store.log_recommendation(first_recommendation)
    analytics_store.log_recommendation(recommendation)

    response = client.get(
        "/analytics/recommendations",
        query_string=dump(
            "generic",
            RecommendationHistoryQuery(
                plant_id=plant_id,
                correlation_id="lifecycle-corr-1",
                since=1_735_689_790.0,
                until=1_735_689_900.0,
                limit=1,
            ),
        ),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert [load("generic", Recommendation, item) for item in payload] == [recommendation]


def test_analytics_history_queries_reject_invalid_filters(client, metadata_store) -> None:
    """Analytics history endpoints reject invalid typed filter values."""
    plant_id = metadata_store.upsert_plant(name="Invalid Filter Plant")

    response = client.get(
        "/analytics/health",
        query_string={"plant_id": plant_id, "limit": 0},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "error" in payload

    response = client.get(
        "/analytics/forecasts",
        query_string={"plant_id": plant_id, "horizon_seconds": "not-an-int"},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "error" in payload


def test_list_actuators_returns_persisted_actuators(
    client, metadata_store, sample_plant_id: int
) -> None:
    """List actuators returns stored actuators.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    metadata_store : MetadataStore
        Store used to seed actuator records.
    sample_plant_id : int
        Plant identifier owning the actuator.

    Returns
    -------
    None
        The assertions raise if /actuators output regresses.
    """
    actuator_id = metadata_store.register_actuator(sample_plant_id, "water_pump", 17, 0)

    response = client.get("/actuators")

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert any(actuator["id"] == actuator_id for actuator in payload)


def test_get_alert_history_returns_persisted_events(
    client, alert_store, sample_sensor
) -> None:
    """Alert history endpoint returns persisted alert events.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    alert_store : AlertsStore
        Store used to seed alerts.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor used by the alert.

    Returns
    -------
    None
        The assertions raise if /alerts/history regresses.
    """
    definition = AlertDefinition(
        alert_key="high_temp:temperature",
        plant_id=sample_sensor.plant_id,
        sensor_id=sample_sensor.id,
        source="temperature",
        rule_id="rule-1",
        rule_name="high_temp",
        kind=AlertType.SENSOR,
        persistence_count=3,
        cooldown_seconds=300,
    )
    alert_store.save_alert_definition(definition)

    event = SensorAlertEvent(
        alert_key=definition.alert_key,
        plant_id=definition.plant_id,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Temperature exceeds threshold",
        correlation_id="alert-123",
        reading=ProcessedSensorData(
            plant_id=sample_sensor.plant_id,
            sensor_id=sample_sensor.id,
            timestamp=1234567890.0,
            value=35.0,
            unit="°C",
            topic=Topics.TEMPERATURE,
            correlation_id="alert-123",
            flags={},
            dq_score=1.0,
            imputed=False,
        ),
        threshold_op=">",
        threshold_value=30.0,
    )
    alert_store.save_alert_event(event)

    response = client.get(
        "/alerts/history", query_string=dump("generic", AlertHistoryQuery())
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)

    events = [load_alert_event(item) for item in payload]
    assert any(event.correlation_id == "alert-123" for event in events)


def test_get_active_alerts_excludes_cleared_events(
    client, alert_store, sample_sensor
) -> None:
    """Active alerts endpoint excludes cleared alerts.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    alert_store : AlertsStore
        Store used to seed alerts.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor used by the alert.

    Returns
    -------
    None
        The assertions raise if /alerts/active regresses.
    """
    definition = AlertDefinition(
        alert_key="active:temp",
        plant_id=sample_sensor.plant_id,
        sensor_id=sample_sensor.id,
        source="temperature",
        rule_id="rule-active",
        rule_name="active_temp",
        kind=AlertType.SENSOR,
        persistence_count=1,
        cooldown_seconds=300,
    )
    alert_store.save_alert_definition(definition)

    alert_store.save_alert_event(
        SensorAlertEvent(
            alert_key=definition.alert_key,
            plant_id=definition.plant_id,
            timestamp=1234567890.0,
            status=AlertStatus.ACTIVE,
            severity=SeverityLevel.WARNING,
            message="Active alert",
            correlation_id="corr-active",
            reading=ProcessedSensorData(
                plant_id=sample_sensor.plant_id,
                sensor_id=sample_sensor.id,
                timestamp=1234567890.0,
                value=35.0,
                unit="°C",
                topic=Topics.TEMPERATURE,
                correlation_id="corr-active",
                flags={},
                dq_score=1.0,
                imputed=False,
            ),
            threshold_op=">",
            threshold_value=30.0,
        )
    )

    alert_store.save_alert_event(
        SensorAlertEvent(
            alert_key=definition.alert_key,
            plant_id=definition.plant_id,
            timestamp=1234567891.0,
            status=AlertStatus.CLEARED,
            severity=SeverityLevel.WARNING,
            message="Cleared alert",
            correlation_id="corr-cleared",
            reading=ProcessedSensorData(
                plant_id=sample_sensor.plant_id,
                sensor_id=sample_sensor.id,
                timestamp=1234567891.0,
                value=33.0,
                unit="°C",
                topic=Topics.TEMPERATURE,
                correlation_id="corr-cleared",
                flags={},
                dq_score=1.0,
                imputed=False,
            ),
            threshold_op=">",
            threshold_value=30.0,
            cleared_ts=1234567891.0,
        )
    )

    response = client.get(
        "/alerts/active", query_string=dump("generic", ActiveAlertsQuery())
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)

    events = [load_alert_event(item) for item in payload]
    assert all(event.status != AlertStatus.CLEARED for event in events)


def test_ensure_alert_definition_is_idempotent(
    client, alert_store, sample_sensor
) -> None:
    """Ensure alert definition endpoint upserts without duplication.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    alert_store : AlertsStore
        Store used to validate persistence.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor used by the definition.

    Returns
    -------
    None
        The assertions raise if /alerts/definitions regresses.
    """
    definition = AlertDefinition(
        alert_key="high_temp:temperature",
        plant_id=sample_sensor.plant_id,
        sensor_id=sample_sensor.id,
        source="temperature",
        rule_id="rule-1",
        rule_name="high_temp",
        kind=AlertType.SENSOR,
        persistence_count=3,
        cooldown_seconds=300,
    )

    payload = dump("generic", definition)
    first = client.post("/alerts/definitions", json=payload)
    second = client.post("/alerts/definitions", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200

    with alert_store.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT COUNT(*) FROM alert_definitions WHERE alert_key = :key AND plant_id = :plant_id"
            ),
            {"key": definition.alert_key, "plant_id": definition.plant_id},
        ).scalar_one()
    assert rows == 1
