from enum import StrEnum


class Topics(StrEnum):
    """MQTT topics for communication between the modules"""

    _PREFIX_SENSOR = "dt.sensors."
    SENSORS_DATA = _PREFIX_SENSOR + "data"
    TEMPERATURE = _PREFIX_SENSOR + "temperature"
    HUMIDITY = _PREFIX_SENSOR + "humidity"
    SOIL_MOISTURE = _PREFIX_SENSOR + "soil_moisture"
    LIGHT_INTENSITY = _PREFIX_SENSOR + "light_intensity"
    CAMERA_IMAGE = _PREFIX_SENSOR + "camera_image"

    @classmethod
    def list_topics(cls) -> list["Topics"]:
        """Get all topics"""
        return [topic for topic in cls if topic not in (cls.SENSORS_DATA, cls._PREFIX_SENSOR)]

    @property
    def raw(self) -> str:
        """Raw topic name"""
        split = self.value.split(".")
        raw_name = f"{'.'.join(split[:-1])}.raw"
        return f"{raw_name}.{self.short_name}"

    @property
    def processed(self) -> str:
        """Processed topic name"""
        split = self.value.split(".")
        processed_name = f"{'.'.join(split[:-1])}.processed"
        return f"{processed_name}.{self.short_name}"

    @classmethod
    def from_short_name(cls, short_name: str) -> "Topics":
        """Get the topic from the short name"""
        return cls[short_name.upper()]

    @property
    def short_name(self) -> str:
        """Get the short name of the topic"""
        return self.value.split(".")[-1]
