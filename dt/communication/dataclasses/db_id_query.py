from dataclasses import dataclass

from dt.communication.dataclasses.serializable import JsonSerializable
from dt.communication.topics import Topics


@dataclass
class DBIdQuery(JsonSerializable):
    """Represents a query to the database to get the data from a specific sensor id.

    Attributes
    ----------
    sensor_id : The id of the sensor.
    limit : The maximum number of data points to return.
    """

    sensor_id: int
    limit: int

    def __post_init__(self):
        self.sensor_id = int(self.sensor_id)
        self.limit = int(self.limit)
        if self.limit < 1:
            raise ValueError("Limit must be greater than 0")
        if self.sensor_id < 1:
            raise ValueError("Sensor id must be greater than 0")
