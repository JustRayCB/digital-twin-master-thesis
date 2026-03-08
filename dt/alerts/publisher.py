"""Alert event publisher.

Publishes alert history events to Kafka for downstream consumption.
"""

import time

from dt.communication.messaging_service import MessagingService
from dt.communication.topics import Topics
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertHistoryEvent,
    AlertStatus,
)
from dt.utils import get_logger


class AlertPublisher:
    """Publishes alert history events to Kafka.

    This class wraps a MessagingService producer and publishes AlertHistoryEvent
    subtypes (SensorAlertEvent, ExternalAlertEvent) to the alerts topic.

    Attributes
    ----------
    messaging_service : MessagingService
        The messaging service instance for publishing.
    definition_client : Any
        Client used to persist alert definitions before publishing events.
    """

    def __init__(self, messaging_service: MessagingService, definition_client) -> None:
        """Initialize the alert publisher.

        Parameters
        ----------
        messaging_service : MessagingService
            The messaging service instance for publishing.
        definition_client : Any
            Client used to persist alert definitions before publishing events.
        """
        self.messaging_service = messaging_service
        self.definition_client = definition_client
        self.logger = get_logger(__name__)

    def publish(
        self,
        definition: AlertDefinition,
        alert_event: AlertHistoryEvent,
    ) -> bool:
        """Publish an alert history event to Kafka.

        Ensures the alert definition is persisted, updates timestamps,
        and publishes the AlertHistoryEvent subclass to Kafka.

        Parameters
        ----------
        definition : AlertDefinition
            Definition associated with the alert.
        alert_event : AlertHistoryEvent
            The alert history event to publish (SensorAlertEvent or ExternalAlertEvent).
        actor : str | None, optional
            Actor identifier for ACKNOWLEDGED/CLEARED events.

        Returns
        -------
        bool
            True if the message was published successfully, False otherwise.
        """
        try:
            self.definition_client.ensure_alert_definition(definition)
        except Exception as exc:
            self.logger.error(
                "Failed to persist alert definition before publishing",
                extra={"alert_key": definition.alert_key, "plant_id": definition.plant_id},
            )
            raise RuntimeError("Unable to persist alert definition") from exc

        if alert_event.status == AlertStatus.ACKNOWLEDGED:
            alert_event.acknowledged_ts = time.time()
            if alert_event.acknowledged_by is None:
                raise ValueError(
                    "Alert acknowledged_by (actor) must be set for ACKNOWLEDGED alerts befor publishing"
                )
        elif alert_event.status == AlertStatus.CLEARED:
            alert_event.cleared_ts = time.time()

        return self.messaging_service.publish(Topics.ALERTS, alert_event)
