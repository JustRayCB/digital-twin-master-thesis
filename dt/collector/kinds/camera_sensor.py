from typing_extensions import override

from dt.collector.kinds.base_sensor import Sensor
from dt.communication.topics import Topics


class CameraSensor(Sensor):
    def __init__(self, name: str, pin: int, read_interval: int) -> None:
        super().__init__(name, pin, read_interval)

    @property
    @override
    def unit(self) -> str:
        return "image"  # Camera sensor returns an image ??

    @property
    @override
    def topic(self) -> Topics:
        return Topics.CAMERA_IMAGE

    @override
    def read_sensor(self) -> float:
        # TODO: Implement camera sensor reading logic
        raise NotImplementedError("Camera sensor read not implemented yet")
