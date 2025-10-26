from dataclasses import dataclass

from dt.communication.dataclasses.serializable import JsonSerializable


@dataclass
class DBIdQuery(JsonSerializable):
    """Represents a query to retrieve data for a specific sensor ID.

    This dataclass defines the structure for a query that fetches a limited
    number of recent data points for a given sensor from the database.

    Attributes
    ----------
    sensor_id : int
        The unique identifier of the sensor for which to retrieve data. Must be
        greater than 0.
    limit : int
        The maximum number of data points to return. Must be greater than 0.
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
