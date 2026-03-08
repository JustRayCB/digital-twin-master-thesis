from enum import StrEnum

from dt.utils.exceptions import NonProcessableTopic

PREFIX_SENSOR = "dt.sensors."


class Topics(StrEnum):
    """Defines the messaging topics used for communication between modules.

    This enumeration centralizes all topic strings, providing a single source
    of truth and reducing the risk of typos. It also includes helper methods
    for manipulating topic strings, such as generating raw and processed
    variants.
    """

    TEMPERATURE = PREFIX_SENSOR + "temperature"
    HUMIDITY = PREFIX_SENSOR + "humidity"
    SOIL_MOISTURE = PREFIX_SENSOR + "soil_moisture"
    LIGHT_INTENSITY = PREFIX_SENSOR + "light_intensity"
    CAMERA_IMAGE = PREFIX_SENSOR + "camera_image"
    ALERTS = "dt.alerts"
    ACTIONS = "dt.actions"

    @classmethod
    def list_topics(cls) -> list["Topics"]:
        """Get a list of all topics.

        Returns
        -------
        list[Topics]
            A list of all topics
        """
        return list(cls)

    @classmethod
    def list_sensor_topics(cls) -> list["Topics"]:
        """Get a list of all sensor-related topics.

        Returns
        -------
        list[Topics]
            A list of all sensor-related topics
        """
        return [topic for topic in cls if topic.value.startswith(PREFIX_SENSOR)]

    @property
    def raw(self) -> str:
        """Return the raw version of the topic name.

        For a topic like "dt.sensors.temperature", this will return
        "dt.sensors.raw.temperature".

        Returns
        -------
        str
            The raw topic name.
        """
        if PREFIX_SENSOR not in self.value:
            raise NonProcessableTopic(
                "Raw topic is only available for sensor topics. e.g dt.sensors.temperature"
            )
        split = self.value.split(".")
        raw_name = f"{'.'.join(split[:-1])}.raw"
        return f"{raw_name}.{self.short_name}"

    @property
    def processed(self) -> str:
        """Return the processed version of the topic name.

        For a topic like "dt.sensors.temperature", this will return
        "dt.sensors.processed.temperature".

        Returns
        -------
        str
            The processed topic name.
        """
        if PREFIX_SENSOR not in self.value:
            raise NonProcessableTopic(
                "Processed topic is only available for sensor topics. e.g dt.sensors.temperature"
            )
        split = self.value.split(".")
        processed_name = f"{'.'.join(split[:-1])}.processed"
        return f"{processed_name}.{self.short_name}"

    @classmethod
    def from_short_name(cls, short_name: str) -> "Topics":
        """Get a topic enumeration member from its short name.

        For example, `from_short_name("temperature")` will return
        `Topics.TEMPERATURE`.

        Parameters
        ----------
        short_name : str
            The short name of the topic (e.g., "temperature").

        Returns
        -------
        Topics
            The corresponding topic enumeration member.
        """
        """Get the topic from the short name"""
        return cls[short_name.upper()]

    @property
    def short_name(self) -> str:
        """Get the short name of the topic.

        For a topic like "dt.sensors.temperature", this will return
        "temperature".

        Returns
        -------
        str
            The short name of the topic.
        """
        """Get the short name of the topic"""
        return self.value.split(".")[-1]
