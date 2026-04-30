from dataclasses import dataclass


@dataclass
class RecommendationHistoryQuery:
    """Query parameters for persisted recommendation history retrieval."""

    plant_id: int
    since: float | None = None
    until: float | None = None
    limit: int | None = None
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        self.plant_id = int(self.plant_id)
        if self.since is not None:
            self.since = float(self.since)
        if self.until is not None:
            self.until = float(self.until)
        if self.since is not None and self.until is not None and self.since > self.until:
            raise ValueError("since must be less than or equal to until")
        if self.limit is not None:
            self.limit = int(self.limit)
        if self.limit is not None and self.limit <= 0:
            raise ValueError("limit must be positive")
        if self.correlation_id is not None:
            self.correlation_id = str(self.correlation_id)
