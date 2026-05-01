from dataclasses import dataclass


@dataclass
class ActionHistoryQuery:
    """Query parameters for controller action history retrieval."""

    plant_id: int | None = None
    limit: int | None = 50
    since: float | None = None
    until: float | None = None

    def __post_init__(self) -> None:
        if self.plant_id is None:
            raise ValueError("plant_id is required")
        self.plant_id = int(self.plant_id)
        if self.plant_id <= 0:
            raise ValueError("plant_id must be positive")
        if self.limit is not None:
            self.limit = int(self.limit)
        if self.limit is not None and self.limit <= 0:
            raise ValueError("limit must be positive")
        if self.since is not None:
            self.since = float(self.since)
        if self.until is not None:
            self.until = float(self.until)
        if (
            self.since is not None
            and self.until is not None
            and self.since > self.until
        ):
            raise ValueError("since must be less than or equal to until")

    @property
    def effective_limit(self) -> int | None:
        if self.since is not None or self.until is not None:
            return None
        return self.limit
