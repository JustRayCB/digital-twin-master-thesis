import sys

sys.dont_write_bytecode = True


from time import sleep

from dt.sensors import MockMoistureSensor, Sensor, SensorManager
from dt.utils import get_logger


def main():
    logger = get_logger(__name__)
    logger.info("Starting main")

    sensor_manager = SensorManager()
    moisture_sensor = MockMoistureSensor("moisture_sensor", 5, 100)
    sensor_manager.add_sensor(moisture_sensor)

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
