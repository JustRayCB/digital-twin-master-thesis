from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ActuatorConfig:
    """Actuator policy configuration.

    Attributes
    ----------
    pin : Optional[int]
        Physical pin used by a concrete actuator driver when applicable.
    max_duration_seconds : Optional[float]
        Maximum accepted ON duration for a single action command.
    min_cooldown_seconds : Optional[float]
        Minimum elapsed time required between consecutive accepted actions.
    allow_overlap : Optional[bool]
        Whether concurrent actions for the same actuator are allowed.
    allowed_commands : Optional[List[str]]
        Whitelisted command values (for example ``["ON", "OFF"]``).
    """

    pin: Optional[int] = None
    max_duration_seconds: Optional[float] = None
    min_cooldown_seconds: Optional[float] = None
    allow_overlap: Optional[bool] = None
    allowed_commands: Optional[List[str]] = None
