from dataclasses import dataclass
from typing import Optional


@dataclass
class ActionDispatch:
    """Client payload for dispatching an action command."""

    plant_id: int
    actuator_id: int
    command: str
    source: str
    duration: float = 0.0
    reason: Optional[str] = None
    action_id: Optional[str] = None
    correlation_id: Optional[str] = None

    def __post_init__(self) -> None:
        self.plant_id = int(self.plant_id)
        self.actuator_id = int(self.actuator_id)
        self.command = str(self.command)
        self.source = str(self.source)
        self.duration = float(self.duration)
        if self.reason is not None:
            self.reason = str(self.reason)
        if self.action_id is not None:
            self.action_id = str(self.action_id)
        if self.correlation_id is not None:
            self.correlation_id = str(self.correlation_id)

        if self.plant_id <= 0:
            raise ValueError("plant_id must be > 0")
        if self.actuator_id <= 0:
            raise ValueError("actuator_id must be > 0")
        if not self.command.strip():
            raise ValueError("command must be non-empty")
        if self.source not in {"ai", "manual"}:
            raise ValueError("source must be one of: ai, manual")
        if self.duration < 0:
            raise ValueError("duration must be >= 0")
        if self.reason is not None and not self.reason.strip():
            raise ValueError("reason must be non-empty when provided")
        if self.action_id is not None and not self.action_id.strip():
            raise ValueError("action_id must be non-empty when provided")
        if self.correlation_id is not None and not self.correlation_id.strip():
            raise ValueError("correlation_id must be non-empty when provided")
