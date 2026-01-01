from dataclasses import dataclass


@dataclass
class ActionCommand:
    """Represents a command to be sent to an actuator.

    This dataclass defines the structure of a command sent to an actuator
    to perform a specific action, such as turning a device on or off. It
    includes metadata such as the plant and actuator IDs, timestamp, duration,
    the command itself, the reason for the command, and a correlation ID for
    tracing.

    Attributes
    ----------
    plant_id : int
        The unique identifier for the plant associated with the action.
    action_id : str
        A unique identifier for this specific action command.
    actuator_id : int
        The unique identifier for the target actuator.
    timestamp : float
        The Unix timestamp when the command was generated.
    duration : float
        The duration of the action in seconds.
    command : str
        The command to be executed by the actuator (e.g., "ON", "OFF").
    reason : str
        The reason for issuing the command (e.g., "moisture below threshold").
    correlation_id : str
        A unique identifier for tracing the command through the system.
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
