"""Analytics Kafka consumer service."""

from datetime import datetime, timezone

from dt.analytics.alerts.service import AlertEngineService
from dt.analytics.features.base import FeatureSet
from dt.analytics.features.extractor import FeatureExtractor
from dt.analytics.features.recent_window import RecentReadingsWindow
from dt.analytics.models.classification import PlantHealthBaselineModel
from dt.analytics.models.prediction.moisture_forecaster import \
    RecursiveLeastSquaresForecaster
from dt.analytics.policies.engine import RecommendationPolicyEngine
from dt.analytics.publisher import AnalyticsPublisher
from dt.communication.dataclasses import AggregatedReading, ProcessedSensorData
from dt.communication.dataclasses.analytics import (ForecastResult,
                                                    HealthAssessment,
                                                    HealthState,
                                                    Recommendation)
from dt.communication.dataclasses.queries import ReadingsQuery
from dt.communication.db_client import DatabaseApiClient
from dt.communication.messaging_service import MessagingService
from dt.communication.topics import Topics
from dt.utils import get_logger

_LONGER_CONTEXT_WINDOW_SECONDS = 86_400.0  # 24 hours, used for providing additional context to feature extraction beyond the recent window


class AnalyticsService:
    """Subscribe to processed sensor topics and dispatch analytics capabilities."""

    def __init__(
        self,
        kafka_service: MessagingService,
        alert_service: AlertEngineService,
        feature_extractor: FeatureExtractor | None = None,
        publisher: AnalyticsPublisher | None = None,
        db_client: DatabaseApiClient | None = None,
        health_model: PlantHealthBaselineModel | None = None,
        recommendation_engine: RecommendationPolicyEngine | None = None,
        recent_window_seconds: int = 7_200,  # 2 hours, the event-time window of recent readings to maintain for feature extraction
        cadence_seconds: int = 900,  # 15 minutes, the minimum time delta between consecutive feature extractions for the same plant
        longer_context_cadence_seconds: int = 3_600,  # 1 hour, the minimum time delta between consecutive longer context refreshes
    ) -> None:
        self.kafka_service = kafka_service
        self.alert_service = alert_service
        self.feature_extractor = feature_extractor or FeatureExtractor()
        self.publisher = publisher or AnalyticsPublisher(kafka_service)
        self.db_client = db_client or DatabaseApiClient()
        self.health_model = health_model or PlantHealthBaselineModel()
        self.recommendation_engine = recommendation_engine or RecommendationPolicyEngine()
        self.recent_window_seconds = int(recent_window_seconds)
        self.cadence_seconds = int(cadence_seconds)
        self.longer_context_cadence_seconds = int(longer_context_cadence_seconds)
        self._recent_windows: dict[int, RecentReadingsWindow] = {}
        self._hydrated_plants: set[int] = set()
        self._last_health_assessment_timestamps: dict[int, float] = {}
        self._last_moisture_forecast_timestamps: dict[int, float] = {}
        self._last_forecast_results: list[ForecastResult] = []
        self._longer_context_aggregates: dict[int, list[AggregatedReading]] = {}
        self._last_longer_context_refresh_timestamps: dict[int, float] = {}
        self._moisture_forecasters: dict[int, RecursiveLeastSquaresForecaster] = {}
        self.logger = get_logger(__name__)

    def start(self) -> None:
        sensor_topics = Topics.list_sensor_topics()
        for topic in sensor_topics:
            if topic in (Topics.CAMERA_IMAGE_TOP, Topics.CAMERA_IMAGE_SIDE):
                continue
            processed_topic = topic.processed
            self.kafka_service.subscribe(processed_topic, self._on_message)
            self.logger.info(f"Subscribed to {processed_topic}")

    def shutdown(self) -> None:
        self.logger.info("Shutting down analytics service")
        self.kafka_service.disconnect()

    def _on_message(self, payload: ProcessedSensorData) -> None:
        self.logger.debug("Received processed payload for analytics: %s", payload.topic.short_name)
        self.alert_service.handle_processed_reading(payload)
        recent_window = self._recent_windows.setdefault(
            payload.plant_id,
            RecentReadingsWindow(window_seconds=self.recent_window_seconds),
        )
        recent_window.insert(payload)

        self._hydrate_recent_window(payload.plant_id, payload.timestamp)
        self._refresh_longer_context_aggregates(payload.plant_id, payload.timestamp)

        should_assess_health = self._should_run(
            self._last_health_assessment_timestamps,
            payload.plant_id,
            payload.timestamp,
        )
        should_forecast_moisture = payload.topic == Topics.SOIL_MOISTURE and self._should_run(
            self._last_moisture_forecast_timestamps,
            payload.plant_id,
            payload.timestamp,
        )
        if not should_assess_health and not should_forecast_moisture:
            return

        features = self.feature_extractor.extract(
            recent_window.snapshot(),
            reference_timestamp=payload.timestamp,
            longer_context_aggregates=self._longer_context_aggregates.get(payload.plant_id, []),
        )
        forecast_results = []
        if should_forecast_moisture:
            forecast_results = self._run_moisture_forecast(payload, features)
            self._last_forecast_results = forecast_results
            self._last_moisture_forecast_timestamps[payload.plant_id] = payload.timestamp

        if should_assess_health:
            health_assessment = self._run_health_assessment(payload, features)
            self._submit_recommendation(health_assessment, self._last_forecast_results)
            self._last_health_assessment_timestamps[payload.plant_id] = payload.timestamp

    def _run_health_assessment(
        self,
        payload: ProcessedSensorData,
        features: FeatureSet,
    ) -> HealthAssessment:
        result = self.health_model.predict(
            plant_id=str(payload.plant_id),
            features=features,
            timestamp=datetime.fromtimestamp(payload.timestamp, tz=timezone.utc),
        )
        assessment = HealthAssessment(
            plant_id=payload.plant_id,
            timestamp=payload.timestamp,
            correlation_id=payload.correlation_id,
            state=HealthState(result.outputs.get("state", HealthState.UNKNOWN.value)),
            score=result.outputs.get("score"),
            summary=result.outputs.get("summary", ""),
            confidence=result.outputs.get("confidence"),
            model_metadata=result.model_metadata,
        )
        self.publisher.publish_health(assessment)
        return assessment

    def _run_moisture_forecast(
        self,
        payload: ProcessedSensorData,
        features: FeatureSet,
    ) -> list[ForecastResult]:
        self.logger.info(f"Running moisture forecast for plant {payload.plant_id}")
        forecaster = self._moisture_forecasters.setdefault(
            payload.plant_id,
            RecursiveLeastSquaresForecaster(),
        )
        result = forecaster.predict(
            plant_id=str(payload.plant_id),
            features=features,
            timestamp=datetime.fromtimestamp(payload.timestamp, tz=timezone.utc),
        )
        if result.outputs.get("error"):
            return []

        horizon_hours = result.outputs.get("horizon_hours") or []
        predicted_values = result.outputs.get("predicted_values") or []
        forecasts: list[ForecastResult] = []
        for horizon_hours_value, predicted_value in zip(horizon_hours, predicted_values):
            self.logger.info(
                f"Moisture forecast for plant {payload.plant_id} at horizon {horizon_hours_value} hours: {predicted_value}%"
            )
            forecast = ForecastResult(
                plant_id=payload.plant_id,
                timestamp=payload.timestamp,
                correlation_id=payload.correlation_id,
                metric="soil_moisture",
                horizon_seconds=int(horizon_hours_value * 3600),
                predicted_value=predicted_value,
                unit="%",
                model_metadata=result.model_metadata,
                features_used=result.features_used,
                inference_metadata=result.metadata,
            )
            self.publisher.publish_forecast(forecast)
            forecasts.append(forecast)
        return forecasts

    def _submit_recommendation(
        self,
        health_assessment: HealthAssessment,
        forecasts: list[ForecastResult],
    ) -> None:
        recommendation: Recommendation | None = self.recommendation_engine.build_recommendation(
            health_assessment,
            forecasts,
        )
        if recommendation is None:
            return

        try:
            self.publisher.publish_recommendation(recommendation)
        except Exception as exc:
            self.logger.error(
                "Recommendation publication failed for plant %s: %s",
                health_assessment.plant_id,
                exc,
            )
            return

        self.logger.info(
            "Published recommendation for plant %s",
            health_assessment.plant_id,
        )

    def _should_run(
        self,
        last_run_timestamps: dict[int, float],
        plant_id: int,
        reference_timestamp: float,
    ) -> bool:
        if self.cadence_seconds <= 0:
            return True

        last_run_timestamp = last_run_timestamps.get(plant_id)
        if last_run_timestamp is None:
            return True

        return reference_timestamp - last_run_timestamp >= self.cadence_seconds

    def _hydrate_recent_window(self, plant_id: int, reference_timestamp: float) -> None:
        if plant_id in self._hydrated_plants:
            return

        historical_readings = self.db_client.query_readings(
            ReadingsQuery(
                plant_id=plant_id,
                window="raw",
                since=reference_timestamp - self.recent_window_seconds,
                until=reference_timestamp,
            )
        )
        recent_window = self._recent_windows[plant_id]
        recent_window.extend(
            [reading for reading in historical_readings if isinstance(reading, ProcessedSensorData)]
        )
        self._hydrated_plants.add(plant_id)

    def _refresh_longer_context_aggregates(self, plant_id: int, reference_timestamp: float) -> None:
        last_refresh = self._last_longer_context_refresh_timestamps.get(plant_id)
        if (
            last_refresh is not None
            and reference_timestamp - last_refresh < self.longer_context_cadence_seconds
        ):
            return

        aggregates = self.db_client.query_readings(
            ReadingsQuery(
                plant_id=plant_id,
                window="1h",
                since=reference_timestamp - _LONGER_CONTEXT_WINDOW_SECONDS,
                until=reference_timestamp,
            )
        )
        self._longer_context_aggregates[plant_id] = [
            aggregate for aggregate in aggregates if isinstance(aggregate, AggregatedReading)
        ]
        self._last_longer_context_refresh_timestamps[plant_id] = reference_timestamp
