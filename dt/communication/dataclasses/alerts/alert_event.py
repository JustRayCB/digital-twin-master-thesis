from dataclasses import dataclass

from dt.alerts.state.models import AlertLifecycleEvent
from dt.communication.dataclasses.alerts.candidate_alert import CandidateAlert
from dt.communication.dataclasses.serializable import JsonSerializable


@dataclass
class AlertEvent(JsonSerializable):
    """Envelope for alert lifecycle events published to Kafka.

    This rich message format preserves all alert context including the lifecycle
    event type, full alert details, and actor information for acknowledgments/clears.

    Attributes
    ----------
    event : AlertLifecycleEvent
        The lifecycle event type (CREATED, UPDATED, ACKNOWLEDGED, CLEARED, etc.).
    plant_id : int
        The plant ID associated with this alert.
    alert_id : str
        Unique identifier for the alert.
    timestamp : float
        Unix timestamp when this message was created.
    alert : CandidateAlert | None
        Full alert details for CREATED/UPDATED events (None for ACK/CLEAR).
    actor : str | None
        Actor identifier for ACKNOWLEDGED/CLEARED events (None otherwise).
    """

    event: AlertLifecycleEvent  # AlertLifecycleEvent as string for JSON serialization
    plant_id: int
    alert_id: str
    timestamp: float
    alert: CandidateAlert | None = None  # None for ACKNOWLEDGED/CLEARED events
    actor: str | None = None

    def __post_init__(self):
        """Validate and convert types after initialization."""
        self.event = AlertLifecycleEvent(self.event)
        self.alert_id = str(self.alert_id)
        self.timestamp = float(self.timestamp)
        self.plant_id = int(self.plant_id)
