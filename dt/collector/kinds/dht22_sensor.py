# dht22_singleton.py
from typing import Optional

import adafruit_dht
import board

from dt.utils.logger import get_logger


class DHT22Singleton:
    """Singleton for the DHT22 temperature and humidity sensor.

    This class ensures that only one instance of the DHT22 sensor is created
    for a given pin, preventing multiple initializations of the same hardware
    device, which can lead to errors.

    NOTE: If Later, the reading of temperature and humidity is multithreaded,
    additional synchronization mechanisms (like threading locks) may be needed
    to ensure thread safety.

    Attributes
    ----------
    _instance : The singleton instance of this class.
    _sensor : The underlying DHT22 sensor object from the adafruit library.
    _pin : The GPIO pin to which the sensor is connected.
    """

    _instance: Optional["DHT22Singleton"] = None
    _sensor: adafruit_dht.DHT22 | None = None
    _pin: board.pin | None = None

    @classmethod
    def get_instance(cls, pin=None):
        """Get the singleton instance of the DHT22 sensor.

        On the first call, this method initializes the DHT22 sensor on the
        specified pin. Subsequent calls will return the existing instance
        without re-initializing it.

        Parameters
        ----------
        pin : board.Pin, optional
            The GPIO pin to which the sensor is connected. This is required
            on the first call to initialize the sensor.

        Returns
        -------
        adafruit_dht.DHT22
            The singleton instance of the DHT22 sensor.

        Raises
        ------
        ValueError
            If the `pin` is not provided on the first initialization.
        """
        logger = get_logger("DHT22Singleton")

        # First time initialization requires a pin
        if cls._instance is None:
            if pin is None:
                raise ValueError("Pin must be provided for first initialization")

            logger.info(f"Initializing DHT22 sensor on pin {pin}")
            cls._pin = pin
            # Create the sensor instance
            cls._sensor = adafruit_dht.DHT22(pin)
            cls._instance = cls()

        return cls._sensor

    @classmethod
    def get_pin(cls):
        """Get the GPIO pin used by the singleton sensor instance.

        Returns
        -------
        Optional[board.Pin]
            The GPIO pin to which the sensor is connected, or None if the
            singleton has not yet been initialized.
        """
        return cls._pin
