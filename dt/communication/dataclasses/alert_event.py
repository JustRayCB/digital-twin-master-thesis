from dataclasses import dataclass

from dt.communication.dataclasses.serializable import JsonSerializable
from dt.communication.topics import Topics


@dataclass
class AlertEvent(JsonSerializable):
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
