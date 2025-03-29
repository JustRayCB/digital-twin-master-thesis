from enum import StrEnum


class MQTTTopics(StrEnum):
    """MQTT topics for communication between the modules"""

    _PREFIX_SENSOR = "dt/sensors/"
    SENSORS_DATA = _PREFIX_SENSOR + "data"
    TEMPERATURE = _PREFIX_SENSOR + "temperature"
    HUMIDITY = _PREFIX_SENSOR + "humidity"
    SOIL_MOISTURE = _PREFIX_SENSOR + "soil_moisture"
    LIGHT_INTENSITY = _PREFIX_SENSOR + "light_intensity"
    CAMERA_IMAGE = _PREFIX_SENSOR + "camera_image"

    @classmethod
    def from_short_name(cls, short_name: str) -> "MQTTTopics":
        """Get the MQTT topic from the short name"""
        return cls[short_name.upper()]

    @property
    def short_name(self) -> str:
        """Get the short name of the topic"""
        return self.value.split("/")[-1]
