from datetime import datetime, timezone

from pyspark.sql.streaming.state import GroupState

from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.dataclasses.state import FlatlineRecord, SensorState
from dt.communication.topics import Topics
from dt.data.preprocess.state import SparkStateProvider, StateProvider


class DummyProvider(StateProvider):
    """Pure-Python implementation used to assert StateProvider contract semantics."""

    def __init__(self) -> None:
        self._last_valid: dict[int, RawSensorData] = {}
        self._flatlines: dict[int, FlatlineRecord] = {}
        self._history: dict[int, list[RawSensorData]] = {}

    def get_last_valid(self, sensor_id: int) -> RawSensorData | None:
        return self._last_valid.get(sensor_id)

    def update(self, sensor_id: int, reading: RawSensorData) -> None:
        self._last_valid[sensor_id] = reading
        history = self._history.setdefault(sensor_id, [])
        history.append(reading)

    def record_flatline(self, sensor_id: int, value: float, timestamp: float) -> None:
        self._flatlines[sensor_id] = FlatlineRecord(value=value, timestamp=timestamp)

    def get_flatline(self, sensor_id: int) -> FlatlineRecord | None:
        return self._flatlines.get(sensor_id)

    def get_recent_history(
        self, sensor_id: int, window_seconds: float, reference_timestamp: float
    ) -> list[RawSensorData]:
        history = self._history.get(sensor_id, [])
        cutoff = reference_timestamp - window_seconds
        trimmed = [row for row in history if row.timestamp >= cutoff]
        self._history[sensor_id] = trimmed
        return trimmed


def _make_reading(sensor_id: int, value: float) -> RawSensorData:
    """Construct a raw reading to exercise state provider behaviour."""
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    return RawSensorData(
        plant_id=1,
        sensor_id=sensor_id,
        timestamp=base_time,
        value=value,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id=f"reading-{sensor_id}",
    )


def test_dummy_provider_tracks_last_valid_reading() -> None:
    """Dummy provider should persist the latest accepted reading."""
    provider = DummyProvider()
    reading = _make_reading(sensor_id=42, value=21.5)

    provider.update(sensor_id=42, reading=reading)

    retrieved = provider.get_last_valid(42)
    assert retrieved is reading


def test_dummy_provider_records_flatline_metadata() -> None:
    """Dummy provider should store flatline metadata for later retrieval."""
    provider = DummyProvider()
    reading = _make_reading(sensor_id=77, value=19.2)

    provider.record_flatline(sensor_id=77, value=reading.value, timestamp=reading.timestamp)

    record = provider.get_flatline(77)
    assert record is not None
    assert record.value == reading.value
    assert record.timestamp == reading.timestamp


def test_dummy_provider_returns_recent_history_window() -> None:
    """Dummy provider should return the recent window respecting cutoffs."""
    provider = DummyProvider()
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    readings = [
        _make_reading(sensor_id=18, value=10.0),
        RawSensorData(
            plant_id=1,
            sensor_id=18,
            timestamp=base_time + 5,
            value=11.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="reading-18-1",
        ),
    ]
    for item in readings:
        provider.update(sensor_id=item.sensor_id, reading=item)

    history = provider.get_recent_history(
        sensor_id=18,
        window_seconds=10,
        reference_timestamp=base_time + 7,
    )

    assert len(history) == 2


class _FakeGroupState(GroupState):
    """Minimal stub implementing the portion of GroupState used in unit tests."""

    def __init__(self, initial_payload: tuple[object, ...] = ()) -> None:
        self._payload = initial_payload
        self._defined = initial_payload is not None

    @property
    def get(self) -> tuple[object, ...]:
        return self._payload

    def update(self, payload: tuple[object, ...]) -> None:
        if not isinstance(payload, tuple):
            raise TypeError("Expected tuple payload")
        self._payload = payload


def test_spark_state_provider_initializes_from_group_state() -> None:
    """SparkStateProvider should hydrate its state from the incoming payload."""
    reading = _make_reading(sensor_id=12, value=20.5)
    seed_state = SensorState(
        last_valid=reading,
        flatline=FlatlineRecord(value=20.5, timestamp=reading.timestamp),
    )
    group_state = _FakeGroupState(initial_payload=seed_state.to_payload())

    provider = SparkStateProvider(group_state=group_state, sensor_id=reading.sensor_id)

    last_valid = provider.get_last_valid(sensor_id=reading.sensor_id)
    assert last_valid is not None
    assert last_valid.value == reading.value
    flatline = provider.get_flatline(sensor_id=reading.sensor_id)
    assert flatline is not None
    assert flatline.value == 20.5


def test_spark_state_provider_persists_updates() -> None:
    """SparkStateProvider should persist updates back to Spark."""
    group_state = _FakeGroupState()
    provider = SparkStateProvider(group_state=group_state, sensor_id=88)
    reading = _make_reading(sensor_id=88, value=19.7)

    provider.update(sensor_id=88, reading=reading)

    persisted_tuple = group_state.get
    assert persisted_tuple is not None
    persisted_state = SensorState.from_payload(persisted_tuple)
    assert persisted_state.last_valid is not None
    assert persisted_state.last_valid.value == reading.value
    assert persisted_state.flatline is None


def test_spark_state_provider_records_flatline_in_group_state() -> None:
    """SparkStateProvider should record flatline metadata in Spark's storage."""
    group_state = _FakeGroupState()
    provider = SparkStateProvider(group_state=group_state, sensor_id=88)

    provider.record_flatline(sensor_id=88, value=11.3, timestamp=123.4)

    persisted_tuple = group_state.get
    assert persisted_tuple is not None
    persisted_state = SensorState.from_payload(persisted_tuple)
    flatline = persisted_state.flatline
    assert flatline is not None
    assert flatline.value == 11.3
    assert flatline.timestamp == 123.4


def test_spark_state_provider_tracks_recent_history() -> None:
    """SparkStateProvider should return history trimmed to the requested window."""
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    group_state = _FakeGroupState()
    provider = SparkStateProvider(group_state=group_state, sensor_id=55)
    first = RawSensorData(
        plant_id=1,
        sensor_id=55,
        timestamp=base_time - 30,
        value=17.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="reading-55-0",
    )
    second = RawSensorData(
        plant_id=1,
        sensor_id=55,
        timestamp=base_time - 5,
        value=21.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="reading-55-1",
    )

    provider.update(sensor_id=55, reading=first)
    provider.update(sensor_id=55, reading=second)

    history = provider.get_recent_history(
        sensor_id=55,
        window_seconds=20,
        reference_timestamp=base_time,
    )

    assert len(history) == 1
    assert history[0].value == second.value


def test_spark_state_provider_trims_persisted_history() -> None:
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    group_state = _FakeGroupState()
    provider = SparkStateProvider(group_state=group_state, sensor_id=91)
    samples = [
        RawSensorData(
            plant_id=1,
            sensor_id=91,
            timestamp=base_time - 120,
            value=10.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="reading-91-0",
        ),
        RawSensorData(
            plant_id=1,
            sensor_id=91,
            timestamp=base_time - 10,
            value=12.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="reading-91-1",
        ),
    ]
    for item in samples:
        provider.update(sensor_id=91, reading=item)

    history = provider.get_recent_history(
        sensor_id=91,
        window_seconds=30,
        reference_timestamp=base_time,
    )

    assert len(history) == 1
    persisted_tuple = group_state.get
    assert persisted_tuple is not None
    persisted_state = SensorState.from_payload(persisted_tuple)
    assert len(persisted_state.history) == 1
