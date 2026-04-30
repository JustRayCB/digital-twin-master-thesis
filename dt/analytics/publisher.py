"""Analytics event publisher."""

from dt.communication.dataclasses.analytics import (
    ForecastResult,
    HealthAssessment,
    Recommendation,
)
from dt.communication.messaging_service import MessagingService
from dt.communication.topics import Topics


class AnalyticsPublisher:
    """Publish analytics events to analytics topics."""

    def __init__(self, messaging_service: MessagingService) -> None:
        self.messaging_service = messaging_service

    def publish_health(self, payload: HealthAssessment) -> bool:
        return self.messaging_service.publish(Topics.ANALYTICS_HEALTH, payload)

    def publish_forecast(self, payload: ForecastResult) -> bool:
        return self.messaging_service.publish(Topics.ANALYTICS_FORECAST, payload)

    def publish_recommendation(self, payload: Recommendation) -> bool:
        return self.messaging_service.publish(Topics.RECOMMENDATIONS_SUBMITTED, payload)
