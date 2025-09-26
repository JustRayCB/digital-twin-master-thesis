from typing_extensions import override

from dt.collector.kinds.base_sensor import Sensor


class CameraSensor(Sensor):
    def __init__(self, name: str, pin: int, read_interval: int) -> None:
        super().__init__(name, pin, read_interval)

    @property
    @override
    def unit(self) -> str:
        return "image"  # Camera sensor returns an image ??

    @override
    def read_sensor(self) -> float:
        pass

    @override
    def process_data(self, raw_data: float) -> float:
        pass
