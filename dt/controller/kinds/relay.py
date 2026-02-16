import RPi.GPIO as GPIO

from dt.communication.dataclasses.controller import ActuatorConfig
from dt.utils import get_logger

logger = get_logger(__name__)


class RelayDriver:
    """GPIO relay driver (active-low)."""

    def __init__(self, name: str, config: ActuatorConfig):
        self.name = name
        self.config = config
        self.pin = self.config.pin
        self._setup_gpio()

    def _setup_gpio(self) -> None:
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self.pin, GPIO.OUT, initial=GPIO.HIGH)
            logger.info(f"Initialized relay {self.name} on pin {self.pin} (active-low)")
        except Exception as exc:
            logger.error(f"Failed to setup GPIO for {self.name}: {exc}")

    def execute(self, command: str) -> bool:
        cmd_upper = command.upper()

        if cmd_upper not in ["ON", "OFF"]:
            logger.error(f"Invalid command for relay {self.name}: {command}")
            return False

        try:
            state = GPIO.LOW if cmd_upper == "ON" else GPIO.HIGH
            GPIO.output(self.pin, state)
            logger.info(f"Relay {self.name} (pin {self.pin}) set to {cmd_upper}")
            return True
        except Exception as exc:
            logger.error(f"GPIO error executing {command} on {self.name}: {exc}")
            return False

    def cleanup(self) -> None:
        try:
            GPIO.output(self.pin, GPIO.HIGH)
        except Exception as exc:
            logger.error(f"Error cleaning up {self.name}: {exc}")
