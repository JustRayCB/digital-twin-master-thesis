from dataclasses import dataclass


@dataclass
class AlertHistoryQuery:
    """Query parameters for alert history retrieval."""

    plant_id: int | None = None
    limit: int = 100

    def __post_init__(self) -> None:
        if self.plant_id is not None:
            self.plant_id = int(self.plant_id)
        self.limit = int(self.limit) if self.limit is not None else 100
        if self.limit <= 0:
            raise ValueError("limit must be positive")
