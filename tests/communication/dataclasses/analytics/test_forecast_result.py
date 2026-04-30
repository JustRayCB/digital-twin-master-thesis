import pytest

from dt.communication.dataclasses.analytics.forecast_result import ForecastResult
from dt.communication.dataclasses.analytics.model_metadata import ModelMetadata


def test_forecast_result_coerces_values() -> None:
    payload = ForecastResult(
        plant_id="3",
        timestamp="1735000000.5",
        correlation_id=987,
        metric=123,
        horizon_seconds="900",
        predicted_value="41.5",
        unit=789,
    )

    assert payload.plant_id == 3
    assert payload.timestamp == 1_735_000_000.5
    assert payload.correlation_id == "987"
    assert payload.metric == "123"
    assert payload.horizon_seconds == 900
    assert payload.predicted_value == 41.5
    assert payload.unit == "789"


def test_forecast_result_validates_horizon_and_required_ids() -> None:
    with pytest.raises(ValueError, match="horizon_seconds"):
        ForecastResult(
            plant_id=3,
            timestamp=1_735_000_000,
            correlation_id="corr-2",
            metric="soil_moisture",
            horizon_seconds=0,
            predicted_value=20.0,
            unit="%",
        )

    with pytest.raises(ValueError, match="correlation_id"):
        ForecastResult(
            plant_id=3,
            timestamp=1_735_000_000,
            correlation_id="",
            metric="soil_moisture",
            horizon_seconds=900,
            predicted_value=20.0,
            unit="%",
        )


def test_forecast_result_preserves_inference_audit_fields() -> None:
    payload = ForecastResult(
        plant_id=3,
        timestamp=1_735_000_000,
        correlation_id="corr-3",
        metric="soil_moisture",
        horizon_seconds=3600,
        predicted_value=42.0,
        unit="%",
        model_metadata=ModelMetadata(
            model_name="moisture_forecaster",
            model_version="v1",
        ),
        features_used=("soil_moisture.last", "context.soil_moisture_mean_24h"),
        inference_metadata={"confidence": 0.91, "window_size": 24},
    )

    assert payload.model_metadata == ModelMetadata(
        model_name="moisture_forecaster",
        model_version="v1",
    )
    assert payload.features_used == [
        "soil_moisture.last",
        "context.soil_moisture_mean_24h",
    ]
    assert payload.inference_metadata == {
        "confidence": 0.91,
        "window_size": 24,
    }
