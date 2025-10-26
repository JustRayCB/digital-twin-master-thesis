from dataclasses import dataclass

from dt.communication.dataclasses.serializable import JsonSerializable


@dataclass
class AlertEvent(JsonSerializable):
    """Represents an alert event within the system.

    This dataclass defines the structure of an alert, which is generated when
    a system condition deviates from the norm (e.g., low soil moisture).
    Alerts include metadata such as the plant ID, a unique alert ID,
    timestamp, a description of the alert, its severity, and a correlation
    ID for tracing.

    Attributes
    ----------
    plant_id : int
        The unique identifier for the plant associated with the alert.
    alert_id : str
        A unique identifier for this specific alert.
    timestamp : float
        The Unix timestamp when the alert was generated.
    description : str
        A human-readable description of the alert (e.g., "low moisture").
    severity : str
        The severity level of the alert (e.g., "warning", "critical").
    correlation_id : str
        A unique identifier for tracing the alert through the system.
    """

    plant_id: int
    alert_id: str
    timestamp: float
    description: str  # e.g. "low moisture"
    severity: str  # e.g. "warning", "critical" TODO: Enum ?
    correlation_id: str

    def __post_init__(self):
        self.plant_id = int(self.plant_id)
        self.alert_id = str(self.alert_id)
        self.timestamp = float(self.timestamp)
        self.description = str(self.description)
        self.severity = str(self.severity)
        self.correlation_id = str(self.correlation_id)
