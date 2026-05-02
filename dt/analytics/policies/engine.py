"""Policy engine for translating analytics outputs into recommendations."""

from collections.abc import Iterable

from dt.analytics.policies.actions import RecommendationAction
from dt.communication.dataclasses.analytics import (
    ForecastResult,
    HealthAssessment,
    HealthState,
    ModelMetadata,
    Recommendation,
    RecommendedAction,
)


class RecommendationPolicyEngine:
    """Map health and forecast outputs to simple recommendation payloads."""

    def __init__(
        self,
        irrigation_moisture_threshold: float = 45.0,
        irrigation_confidence_threshold: float = 0.55,
        model_metadata: ModelMetadata | None = None,
    ) -> None:
        self.irrigation_moisture_threshold = float(irrigation_moisture_threshold)
        self.irrigation_confidence_threshold = float(irrigation_confidence_threshold)
        self.model_metadata = model_metadata or ModelMetadata(
            model_name="recommendation_policy",
            model_version="v1",
        )

    def build_recommendation(
        self,
        health_assessment: HealthAssessment,
        forecasts: Iterable[ForecastResult],
    ) -> Recommendation | None:
        """Build an actionable recommendation from model outputs."""

        driest_forecast = self._select_driest_soil_moisture_forecast(forecasts)
        recommendation_action = self._select_action(health_assessment, driest_forecast)
        if recommendation_action is None:
            return None

        confidence = self._combine_confidence(health_assessment, driest_forecast)
        if (
            recommendation_action is RecommendationAction.IRRIGATE_NOW
            and confidence < self.irrigation_confidence_threshold
        ):
            recommendation_action = RecommendationAction.INSPECT_PLANT

        return Recommendation(
            plant_id=health_assessment.plant_id,
            timestamp=health_assessment.timestamp,
            correlation_id=health_assessment.correlation_id,
            reason=self._build_reason(
                recommendation_action,
                health_assessment,
                driest_forecast,
                confidence,
            ),
            confidence=confidence,
            actions=self._build_actions(recommendation_action),
            model_metadata=self.model_metadata,
        )

    def _select_action(
        self,
        health_assessment: HealthAssessment,
        driest_forecast: ForecastResult | None,
    ) -> RecommendationAction | None:
        if health_assessment.state is HealthState.UNKNOWN:
            return None

        if (
            driest_forecast is not None
            and health_assessment.state in {HealthState.CRITICAL, HealthState.STRESSED}
            and driest_forecast.predicted_value <= self.irrigation_moisture_threshold
        ):
            return RecommendationAction.IRRIGATE_NOW

        if health_assessment.state is HealthState.STRESSED:
            return RecommendationAction.INSPECT_PLANT

        if health_assessment.state is HealthState.CRITICAL:
            return RecommendationAction.INSPECT_PLANT

        return None

    def _select_driest_soil_moisture_forecast(
        self,
        forecasts: Iterable[ForecastResult],
    ) -> ForecastResult | None:
        soil_moisture_forecasts = [
            forecast for forecast in forecasts if forecast.metric == "soil_moisture"
        ]
        if not soil_moisture_forecasts:
            return None

        return min(
            soil_moisture_forecasts,
            key=lambda forecast: (forecast.predicted_value, forecast.horizon_seconds),
        )

    def _combine_confidence(
        self,
        health_assessment: HealthAssessment,
        driest_forecast: ForecastResult | None,
    ) -> float:
        confidence_values: list[float] = []

        if health_assessment.confidence is not None:
            confidence_values.append(float(health_assessment.confidence))

        if driest_forecast is not None:
            forecast_confidence = (driest_forecast.inference_metadata or {}).get("confidence")
            if forecast_confidence is not None:
                confidence_values.append(float(forecast_confidence))

        if not confidence_values:
            return 0.0

        return max(0.0, min(1.0, min(confidence_values)))

    def _build_reason(
        self,
        action: RecommendationAction,
        health_assessment: HealthAssessment,
        driest_forecast: ForecastResult | None,
        confidence: float,
    ) -> str:
        if driest_forecast is None:
            return health_assessment.summary

        horizon_hours = driest_forecast.horizon_seconds / 3600
        forecast_reason = (
            "soil moisture is forecast to reach "
            f"{driest_forecast.predicted_value:.1f}{driest_forecast.unit} in {horizon_hours:g}h"
        )

        if (
            action is RecommendationAction.INSPECT_PLANT
            and confidence < self.irrigation_confidence_threshold
        ):
            return (
                f"{health_assessment.summary}; {forecast_reason}; confidence is too limited "
                "for automatic irrigation"
            )

        return f"{health_assessment.summary}; {forecast_reason}"

    def _build_actions(self, recommendation_action: RecommendationAction) -> list[RecommendedAction]:
        if recommendation_action is RecommendationAction.IRRIGATE_NOW:
            return [
                RecommendedAction(capability="irrigation", command="ON", duration_seconds=8.0)
            ]
        if recommendation_action is RecommendationAction.INSPECT_PLANT:
            return [RecommendedAction(capability="advisory", command="inspect_plant")]
        return []
