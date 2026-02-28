from dataclasses import dataclass

from dt.communication.topics import Topics


@dataclass
class CameraSnapshot:
    plant_id: int
    sensor_id: int
    timestamp: float
    topic: Topics
    correlation_id: str
    mime_type: str
    image: str
    width: int | None = None
    height: int | None = None

    def __post_init__(self) -> None:
        self.plant_id = int(self.plant_id)
        self.sensor_id = int(self.sensor_id)
        self.timestamp = float(self.timestamp)
        self.topic = Topics(self.topic)
        self.correlation_id = str(self.correlation_id)
        self.mime_type = str(self.mime_type)
        self.image = str(self.image)
        self.width = int(self.width) if self.width is not None else None
        self.height = int(self.height) if self.height is not None else None
