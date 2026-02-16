from typing import Optional, Protocol

from dt.communication.dataclasses.controller import ActuatorConfig


class ActuatorDriver(Protocol):
    def execute(self, command: str) -> bool:
        ...

    def cleanup(self) -> None:
        ...


class BaseActuator:
    """Base class for all actuators."""

    def __init__(
        self,
        actuator_id: int,
        name: str,
        plant_id: int,
        driver: ActuatorDriver,
        config: Optional[ActuatorConfig] = None,
    ):
        self.actuator_id = actuator_id
        self.name = name
        self.plant_id = plant_id
        self.driver = driver
        self.config = config or ActuatorConfig()

    def execute(self, command: str) -> bool:
        return self.driver.execute(command)

    def cleanup(self) -> None:
        self.driver.cleanup()
