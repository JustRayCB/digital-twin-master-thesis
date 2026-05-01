from dataclasses import dataclass


@dataclass
class AnalyticsExportQuery:
    """Query parameters for exporting model-training data from the dashboard."""

    plant_id: int = 1
    since: float | None = None
    until: float | None = None
    limit: int | None = 1000

    def __post_init__(self) -> None:
        self.plant_id = int(self.plant_id)
        if self.plant_id <= 0:
            raise ValueError("plant_id must be positive")

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

    @property
    def effective_limit(self) -> int | None:
        if self.since is not None or self.until is not None:
            return None
        return self.limit
