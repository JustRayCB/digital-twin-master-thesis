# dht22_singleton.py
import adafruit_dht
import board

from dt.utils.logger import get_logger


class DHT22Singleton:
    """
    Singleton class for DHT22 temperature/humidity sensor.
    Ensures only a single instance of the sensor is created across the application.
    """

    _instance = None
    _sensor = None
    _pin = None

    @classmethod
    def get_instance(cls, pin=None):
        """
        Returns the singleton instance of the DHT22 sensor.

        Parameters
        ----------
        pin : board.Pin, optional
            The GPIO pin the sensor is connected to. Required on first call.

        Returns
        -------
        adafruit_dht.DHT22
            The DHT22 sensor instance

        Raises
        ------
        ValueError
            If pin is not provided on first initialization
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
        """Returns the pin used by the sensor"""
        return cls._pin
