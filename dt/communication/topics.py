from enum import StrEnum

PREFIX_SENSOR = "dt.sensors."


class Topics(StrEnum):
    """MQTT topics for communication between the modules"""

    SENSORS_DATA = PREFIX_SENSOR + "data"
    TEMPERATURE = PREFIX_SENSOR + "temperature"
    HUMIDITY = PREFIX_SENSOR + "humidity"
    SOIL_MOISTURE = PREFIX_SENSOR + "soil_moisture"
    LIGHT_INTENSITY = PREFIX_SENSOR + "light_intensity"
    CAMERA_IMAGE = PREFIX_SENSOR + "camera_image"
    ALERTS = "dt.alerts"
    ACTIONS = "dt.actions"

    @classmethod
    def list_topics(cls) -> list["Topics"]:
        """Get all topics"""
        return [topic for topic in cls if topic not in (cls.SENSORS_DATA, PREFIX_SENSOR)]

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
