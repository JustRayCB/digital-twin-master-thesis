"""Alert event publisher.

Wraps MessagingService producer to publish alert lifecycle events to Kafka.
"""

import time

from dt.alerts.state.models import AlertLifecycleEvent
from dt.communication import MessagingService, Topics
from dt.communication.dataclasses.alerts import AlertEvent, CandidateAlert


class AlertPublisher:
    """Publishes alert lifecycle events to Kafka.

    This class wraps a MessagingService producer and converts alert state
    information into AlertEvent messages for publishing to the alerts topic.

    Attributes
    ----------
    messaging_service : MessagingService
        The messaging service instance for publishing.
    plant_id : int
        The plant ID to include in published alert events.
    """

    def __init__(self, messaging_service: MessagingService, plant_id: int) -> None:
        """Initialize the alert publisher.

        Parameters
        ----------
        messaging_service : MessagingService
            The messaging service instance for publishing.
        plant_id : int
            The plant ID to include in published alert events.
        """
        self.messaging_service = messaging_service
        self.plant_id = plant_id

    def publish(
        self,
        event: AlertLifecycleEvent,
        payload: CandidateAlert | str,
        actor: str | None = None,
    ) -> bool:
        """Publish an alert lifecycle event to Kafka.

        Creates a rich AlertMessage envelope that preserves all alert context
        including lifecycle event, full alert details, and actor information.

        Parameters
        ----------
        event : AlertLifecycleEvent
            The lifecycle event type (CREATED, UPDATED, ACKNOWLEDGED, etc.).
        payload : Union[CandidateAlert, str]
            Either a CandidateAlert (for CREATED/UPDATED) or an alert_id string
            (for ACKNOWLEDGED/CLEARED).
        actor : str | None, optional
            Actor identifier for ACKNOWLEDGED/CLEARED events.

        Returns
        -------
        bool
            True if the message was published successfully, False otherwise.
        """
        # Build AlertMessage envelope
        if isinstance(payload, CandidateAlert):
            alert_event = self._create_alert_event(event, payload)
        elif isinstance(payload, str):
            # For lifecycle events (acknowledge/clear), minimal message
            alert_event = self._create_lifecycle_event(event, payload, actor)
        else:
            raise TypeError(f"Unexpected payload type: {type(payload)}")

        return self.messaging_service.publish(Topics.ALERTS, alert_event)

    def _create_alert_event(
        self, event: AlertLifecycleEvent, candidate: CandidateAlert
    ) -> AlertEvent:
        """Create AlertMessage from CandidateAlert for CREATED/UPDATED events.

        Parameters
        ----------
        event : AlertLifecycleEvent
            The lifecycle event type.
        candidate : CandidateAlert
            The candidate alert with full details.

        Returns
        -------
        AlertMessage
            Rich message preserving all alert context.
        """
        # Serialize CandidateAlert to dict for the envelope

        return AlertEvent(
            event=event,
            alert_id=candidate.alert_id,
            timestamp=time.time(),
            plant_id=self.plant_id,
            alert=candidate,
            actor=None,
        )

    def _create_lifecycle_event(
        self, event: AlertLifecycleEvent, alert_id: str, actor: str | None
    ) -> AlertEvent:
        """Create AlertMessage for lifecycle events (ACK/CLEAR).

        Parameters
        ----------
        event : AlertLifecycleEvent
            The lifecycle event type.
        alert_id : str
            The alert ID.
        actor : str | None
            Actor who performed the action.

        Returns
        -------
        AlertMessage
            Lifecycle message with actor information.
        """
        return AlertEvent(
            event=event,
            alert_id=alert_id,
            timestamp=time.time(),
            plant_id=self.plant_id,
            alert=None,  # No full alert details for lifecycle events
            actor=actor,
        )
