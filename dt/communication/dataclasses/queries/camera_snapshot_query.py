from dataclasses import dataclass


@dataclass
class CameraSnapshotQuery:
    """Query parameters for camera snapshot retrieval."""

    plant_id: int
    since: float | None = None
    until: float | None = None

    def __post_init__(self) -> None:
        self.plant_id = int(self.plant_id)
        if self.since is not None:
            self.since = float(self.since)
        if self.until is not None:
            self.until = float(self.until)
