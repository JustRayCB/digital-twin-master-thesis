from dataclasses import dataclass


@dataclass
class ReadingsQuery:
    """Query parameters for /readings endpoint."""

    window: str = "raw"  # "raw" or "1h"
    sensor_id: int | None = None
    plant_id: int | None = None
    topic: str | None = None
    since: float | None = None
    until: float | None = None

    def __post_init__(self) -> None:
        self.window = self.window or "raw"
        if self.window not in ("raw", "1h"):
            raise ValueError("window must be 'raw' or '1h'")
        # Cast to appropriate types if provided
        if self.sensor_id is not None:
            self.sensor_id = int(self.sensor_id)
        if self.plant_id is not None:
            self.plant_id = int(self.plant_id)
        if self.topic is not None:
            self.topic = str(self.topic)
            if self.topic.startswith("dt.sensors."):
                self.topic = self.topic.split(".")[-1]
        if self.since is not None:
            self.since = float(self.since)
        if self.until is not None:
            self.until = float(self.until)
