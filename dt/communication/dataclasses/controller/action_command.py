from dataclasses import dataclass


@dataclass
class ActionCommand:
    """Represents a controller action status event.

    This dataclass defines the structure published on the actions topic and
    persisted to the controller history table. Each instance describes one
    status event for an execution attempt, such as running, completed, failed,
    rejected, or skipped.

    Attributes
    ----------
    plant_id : int
        The unique identifier for the plant associated with the action.
    execution_id : str
        Unique identifier for one execution attempt across all of its status
        events.
    action_id : str
        Logical identifier for grouping similar action commands.
    actuator_id : int
        The unique identifier for the target actuator.
    event_at : float
        The Unix timestamp when this status event was emitted.
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
    """

    plant_id: int
    execution_id: str
    action_id: str
    actuator_id: int
    event_at: float
    duration: float  # in seconds
    command: str  # e.g. "ON" TODO: Enum ?
    reason: str  # e.g. "moisture below threshold"
    correlation_id: str
    source: str = "manual"
    routine_id: int | None = None
    status: str | None = None
    error_message: str | None = None

    def __post_init__(self):
        self.plant_id = int(self.plant_id)
        self.execution_id = str(self.execution_id)
        self.action_id = str(self.action_id)
        self.actuator_id = int(self.actuator_id)
        self.event_at = float(self.event_at)
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

        if self.plant_id <= 0:
            raise ValueError("plant_id must be > 0")
        if self.actuator_id <= 0:
            raise ValueError("actuator_id must be > 0")
        if not self.execution_id.strip():
            raise ValueError("execution_id must be non-empty")
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
        if self.event_at < 0:
            raise ValueError("event_at must be >= 0")
        if self.source == "routine" and self.routine_id is None:
            raise ValueError("routine_id is required when source is routine")
