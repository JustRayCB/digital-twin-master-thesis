"""Integration tests for analytics history database API client methods."""

from __future__ import annotations

import pytest

from dt.communication.dataclasses import (
    ActionResult,
    ForecastResult,
    HealthAssessment,
    HealthState,
    Recommendation,
    RecommendedAction,
    ModelMetadata,
)
from dt.communication.dataclasses.queries import (
    ForecastHistoryQuery,
    HealthHistoryQuery,
    RecommendationHistoryQuery,
)
from dt.communication.db_client import DatabaseApiClient
from dt.data.database.analytics_storage import AnalyticsStore

pytestmark = [pytest.mark.requires_timescale]


def test_get_health_history_reads_real_api_payload(
    database_api_client: DatabaseApiClient,
    db_engine,
    metadata_store,
) -> None:
    """Fetch health history from the real database API."""
    plant_id = metadata_store.upsert_plant(name="Health History Plant")
    analytics_store = AnalyticsStore(engine=db_engine)
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
    analytics_store.log_health_assessment(assessment)

    history = database_api_client.get_health_history(
        HealthHistoryQuery(plant_id=plant_id, correlation_id="health-corr-1")
    )

    assert history == [assessment]


def test_get_forecast_history_reads_real_api_payload(
    database_api_client: DatabaseApiClient,
    db_engine,
    metadata_store,
) -> None:
    """Fetch forecast history from the real database API."""
    plant_id = metadata_store.upsert_plant(name="Forecast History Plant")
    analytics_store = AnalyticsStore(engine=db_engine)
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
    analytics_store.log_forecast_result(forecast)

    history = database_api_client.get_forecast_history(
        ForecastHistoryQuery(
            plant_id=plant_id,
            metric="soil_moisture",
            horizon_seconds=3600,
            correlation_id="forecast-corr-1",
        )
    )

    assert history == [forecast]


def test_get_recommendation_history_reads_real_api_payload(
    database_api_client: DatabaseApiClient,
    db_engine,
    metadata_store,
) -> None:
    """Fetch recommendation lifecycle rows from the real database API."""
    plant_id = metadata_store.upsert_plant(name="Recommendation History Plant")
    analytics_store = AnalyticsStore(engine=db_engine)
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

    analytics_store.log_recommendation(recommendation)

    history = database_api_client.get_recommendation_history(
        RecommendationHistoryQuery(
            plant_id=plant_id,
            correlation_id="lifecycle-corr-1",
            limit=1,
        )
    )

    assert history == [recommendation]


def test_analytics_history_methods_wrap_real_request_failures() -> None:
    """Raise RuntimeError when the analytics history API cannot be reached."""
    client = DatabaseApiClient(base_url="http://127.0.0.1:9")

    with pytest.raises(RuntimeError, match="Failed to fetch health history"):
        client.get_health_history(HealthHistoryQuery(plant_id=1))

    with pytest.raises(RuntimeError, match="Failed to fetch forecast history"):
        client.get_forecast_history(ForecastHistoryQuery(plant_id=1))

    with pytest.raises(RuntimeError, match="Failed to fetch recommendation history"):
        client.get_recommendation_history(RecommendationHistoryQuery(plant_id=1))
