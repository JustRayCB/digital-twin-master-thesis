from dataclasses import dataclass


@dataclass
class ActiveAlertsQuery:
    """Query parameters for active alerts retrieval."""

    plant_id: int | None = None

    def __post_init__(self) -> None:
        if self.plant_id is not None:
            self.plant_id = int(self.plant_id)
