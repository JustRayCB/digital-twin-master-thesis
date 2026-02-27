import RPi.GPIO as GPIO

from dt.utils import get_logger

logger = get_logger(__name__)


class RelayDriver:
    """GPIO relay driver (active-low). Singleton implementation."""

    _instance = None

    def __new__(cls, name: str, pin: int):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, name: str, pin: int):
        if self._initialized:
            return
        self.name = name
        self.pin = pin
        self._setup_gpio()
        self._initialized = True

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
