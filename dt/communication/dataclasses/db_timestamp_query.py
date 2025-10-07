from dataclasses import dataclass

from dt.communication.dataclasses.serializable import JsonSerializable
from dt.communication.topics import Topics


@dataclass
class DBTimestampQuery(JsonSerializable):
    """Represents a query to the database to get the data from a specific timestamp.

    Attributes
    ----------
    data_type : The type of data to query.
    since: The start timestamp of the query.
    until: The end timestamp of the query.
    """

    data_type: str
    since: float
    until: float

    def __post_init__(self):
        self.data_type = str(self.data_type)
        self.since = float(self.since)
        self.until = float(self.until)

    def js_to_py_timestamp(self):
        """
        Converts the timestamp from JavaScript format to Python format
        """
        # Convert the timestamp from milliseconds to seconds
        self.since = self.since / 1000
        self.until = self.until / 1000
