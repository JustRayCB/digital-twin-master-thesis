from dataclasses import dataclass


@dataclass
class DBTimestampQuery:
    """Represents a query to retrieve data within a specific time range.

    This dataclass defines the structure for a query that fetches data of a
    specific type from the database within a given timestamp range.

    Attributes
    ----------
    data_type : str
        The type of data to query (e.g., "temperature", "humidity").
    since : float
        The start of the time range as a Unix timestamp.
    until : float
        The end of the time range as a Unix timestamp.
    """

    data_type: str
    since: float
    until: float

    def __post_init__(self):
        self.data_type = str(self.data_type)
        self.since = float(self.since)
        self.until = float(self.until)

    def js_to_py_timestamp(self):
        """Convert timestamps from JavaScript (milliseconds) to Python (seconds).

        This method modifies the `since` and `until` attributes in-place,
        dividing them by 1000 to convert from milliseconds to seconds. This
        is necessary when receiving timestamps from a JavaScript client.
        """
        # Convert the timestamp from milliseconds to seconds
        self.since = self.since / 1000
        self.until = self.until / 1000
