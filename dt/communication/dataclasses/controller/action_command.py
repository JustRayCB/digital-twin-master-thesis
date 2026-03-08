from dataclasses import dataclass
from typing import Optional


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
        Logical identifier for grouping similar action commands.
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
    source : str
        The source of the command (routine | ai | manual).
    routine_id : Optional[int]
        The ID of the routine that generated the command (if source is routine).
    status : Optional[str]
        Execution status persisted by the storage layer (queued, running, completed, failed, rejected, skipped).
    error_message : Optional[str]
        Optional error message if execution failed or was skipped.
    ended_at : Optional[float]
        Optional Unix timestamp when the execution ended.
    """

    plant_id: int
    action_id: str
    actuator_id: int
    started_at: float
    duration: float  # in seconds
    command: str  # e.g. "ON" TODO: Enum ?
    reason: str  # e.g. "moisture below threshold"
    correlation_id: str
    source: str = "manual"
    routine_id: Optional[int] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    ended_at: Optional[float] = None

    def __post_init__(self):
        self.plant_id = int(self.plant_id)
        self.action_id = str(self.action_id)
        self.actuator_id = int(self.actuator_id)
        self.started_at = float(self.started_at)
        self.duration = float(self.duration)
        self.command = str(self.command)
        self.reason = str(self.reason)
        self.correlation_id = str(self.correlation_id)
        self.source = str(self.source)
        if self.routine_id is not None:
            self.routine_id = int(self.routine_id)
        if self.status is not None:
            self.status = str(self.status)
        if self.error_message is not None:
            self.error_message = str(self.error_message)
        if self.ended_at is not None:
            self.ended_at = float(self.ended_at)

        if self.plant_id <= 0:
            raise ValueError("plant_id must be > 0")
        if self.actuator_id <= 0:
            raise ValueError("actuator_id must be > 0")
        if not self.action_id.strip():
            raise ValueError("action_id must be non-empty")
        if not self.command.strip():
            raise ValueError("command must be non-empty")
        if not self.reason.strip():
            raise ValueError("reason must be non-empty")
        if not self.correlation_id.strip():
            raise ValueError("correlation_id must be non-empty")
        if self.source not in {"manual", "ai", "routine"}:
            raise ValueError("source must be one of: manual, ai, routine")
        if self.duration < 0:
            raise ValueError("duration must be >= 0")
        if self.started_at < 0:
            raise ValueError("timestamp must be >= 0")
        if self.source == "routine" and self.routine_id is None:
            raise ValueError("routine_id is required when source is routine")
