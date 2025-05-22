import sys

import board

sys.dont_write_bytecode = True


from time import sleep

from dt.sensors import (HumiditySensor, LightSensor, MockMoistureSensor,
                        SensorManager, SoilMoistureSensor, TemperatureSensor)
from dt.utils import get_logger


def main():
    logger = get_logger(__name__)
    logger.info("Starting main")

    sensor_manager = SensorManager()
    # moisture_sensor = MockMoistureSensor("moisture_sensor", 5, 100)
    # sensor_manager.add_sensor(moisture_sensor)

    """
    TODO: Moisture Sensor and light sensor use i2c buses, so it needs two pins (SCL and SDA)
         I need to change how the constructor of the sensors are defined, the pins here for those 
         sensors are not representative
         Soil moisture uses the GPIO 0 and 1 pins for SCL and SDA respectively
         Light sensor uses the GPIO 2 and 3 pins for SCL and SDA respectively
    """
    moisturee_sensor = SoilMoistureSensor("moisture_sensor", 5, board.D1)
    temperature_sensor = TemperatureSensor("temperature_sensor", 5, board.D23)
    humidity_sensor = HumiditySensor("humidity_sensor", 5, board.D23)
    light_sensor = LightSensor("light_sensor", 5, board.D3)

    sensor_manager.add_sensor(moisturee_sensor)
    sensor_manager.add_sensor(temperature_sensor)
    sensor_manager.add_sensor(humidity_sensor)
    sensor_manager.add_sensor(light_sensor)

    try:
        while True:
            sensor_manager.read_all_sensors()
            print("Reading all sensors")
            sleep(1)
    except KeyboardInterrupt:
        logger.info("Exiting main")
    finally:
        logger.info("Cleaning up")
        del sensor_manager
        logger.info("Exiting")

    pass


if __name__ == "__main__":
    main()
