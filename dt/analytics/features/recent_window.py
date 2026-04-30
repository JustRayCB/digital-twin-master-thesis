"""In-memory recent-window state for per-plant feature extraction."""

from dt.communication.dataclasses import ProcessedSensorData


class RecentReadingsWindow:
    """Maintain a bounded event-time window of processed readings."""

    def __init__(self, window_seconds: int) -> None:
        self.window_seconds = int(window_seconds)
        self._latest_timestamp: float | None = None
        self._readings: list[ProcessedSensorData] = []

    def insert(self, reading: ProcessedSensorData) -> None:
        """Insert one reading and trim stale entries using event time."""
        # TODO: Strengthen this check by comparing sensor_id timestamp, correlation_id,
        # but for now we can rely on the fact that the same reading won't be inserted twice.
        if reading in self._readings:
            return
        self._readings.append(reading)
        if self._latest_timestamp is None or reading.timestamp > self._latest_timestamp:
            self._latest_timestamp = reading.timestamp
        self._trim()

    def extend(self, readings: list[ProcessedSensorData]) -> None:
        """Insert multiple readings into the window."""
        for reading in readings:
            self.insert(reading)

    def snapshot(self) -> list[ProcessedSensorData]:
        """Return a deterministic snapshot sorted by event timestamp."""
        return sorted(self._readings, key=lambda item: (item.timestamp, item.sensor_id))

    def _trim(self) -> None:
        if self._latest_timestamp is None:
            return

        cutoff = self._latest_timestamp - float(self.window_seconds)
        self._readings = [reading for reading in self._readings if reading.timestamp >= cutoff]
