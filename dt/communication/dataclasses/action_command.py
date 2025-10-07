from dataclasses import dataclass

from dt.communication.dataclasses.serializable import JsonSerializable
from dt.communication.topics import Topics


@dataclass
class ActionCommand(JsonSerializable):
    """Represents a command to be sent to an actuator.

    Attributes
    ----------
    actuator_id : The id of the actuator.
    action : The action to be performed by the actuator.
    """

    plant_id: int
    action_id: str
    actuator_id: int
    timestamp: float
    duration: float  # in seconds
    command: str  # e.g. "ON" TODO: Enum ?
    reason: str  # e.g. "moisture below threshold"
    correlation_id: str

    def __post_init__(self):
        self.plant_id = int(self.plant_id)
        self.action_id = str(self.action_id)
        self.actuator_id = int(self.actuator_id)
        self.timestamp = float(self.timestamp)
        self.duration = float(self.duration)
        self.command = str(self.command)
        self.reason = str(self.reason)
        self.correlation_id = str(self.correlation_id)
