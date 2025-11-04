"""Internal alert state dataclasses.

Defines data structures for tracking alert lifecycle and state.
"""

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from dt.alerts.config.alert_rule import SeverityLevel


class AlertLifecycleEvent(StrEnum):
    """Alert lifecycle event types returned by registry operations."""

    CREATED = "created"  # New alert reaches persistence threshold
    UPDATED = "updated"  # Alert persists but not yet across cooldown
    SUPPRESSED = "suppressed"  # Within cooldown period
    IGNORED = "ignored"  # Did not hit persistence threshold yet
    ACKNOWLEDGED = "acknowledged"  # Alert was acknowledged
    CLEARED = "cleared"  # Alert was cleared


@dataclass
class AlertState:
    """Tracks the state of an active alert in the registry.

    Attributes
    ----------
    alert_id : str
        Unique identifier for this alert.
    rule_id : str | None
        The rule that triggered this alert (None for external submissions).
    source : str
        The sensor type or topic short name.
    severity : SeverityLevel
        Severity level of the alert.
    message : str
        Human-readable alert message.
    first_seen : float
        Unix timestamp when alert was first detected.
    last_seen : float
        Unix timestamp when alert was last detected.
    occurrences : int
        Number of times this alert has been detected (for persistence tracking).
    acknowledged : bool
        Whether the alert has been acknowledged.
    acknowledged_by : str | None
        Actor who acknowledged the alert (if acknowledged).
    cooldown_until : float | None
        Unix timestamp until which alert is in cooldown (suppressed).
    correlation_id : str
        Most recent correlation ID associated with this alert.
    """

    alert_id: str
    rule_id: str | None
    source: str
    severity: SeverityLevel
    message: str
    first_seen: float
    last_seen: float
    occurrences: int
    acknowledged: bool
    acknowledged_by: str | None
    cooldown_until: float | None
    correlation_id: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the AlertState to a dictionary."""
        return asdict(self)
