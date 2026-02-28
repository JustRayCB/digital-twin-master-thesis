from dt.controller.kinds.base_actuator import BaseActuator
from dt.controller.kinds.relay import RelayDriver


class Pump(BaseActuator):
    """Water pump actuator."""

    def __init__(self, actuator_id: int, name: str, plant_id: int, pin: int, relay_channel: int):
        super().__init__(
            actuator_id=actuator_id,
            name=name,
            plant_id=plant_id,
            driver=RelayDriver(name, pin),
            pin=pin,
            relay_channel=relay_channel,
        )
