from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from pyspark.sql import Row, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.streaming.state import GroupState, GroupStateTimeout
from pyspark.sql.types import DoubleType, IntegerType, StructField, StructType

from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess.core.state import SensorState, SparkStateProvider

OUTPUT_SCHEMA = StructType(
    [
        StructField("plant_id", IntegerType(), nullable=False),
        StructField("sensor_id", IntegerType(), nullable=False),
        StructField("last_value", DoubleType(), nullable=True),
        StructField("history_len", IntegerType(), nullable=False),
        StructField("flatline_value", DoubleType(), nullable=True),
        StructField("flatline_timestamp", DoubleType(), nullable=True),
    ]
)


def _make_event(
    plant_id: int,
    sensor_id: int,
    timestamp: float,
    value: float,
    unit: str,
    topic: Topics,
    correlation_id: str,
) -> Row:
    return Row(
        plant_id=int(plant_id),
        sensor_id=int(sensor_id),
        timestamp=float(timestamp),
        value=float(value),
        unit=str(unit),
        topic=topic.value,
        correlation_id=correlation_id,
    )


def _run_stateful_stream(
    spark_session: SparkSession,
    workspace: Path,
    events: list[Row],
    max_history_length: int,
    window_seconds: float,
    record_flatline: bool = False,
) -> list[dict[str, float | int | None]]:
    return _run_stateful_stream_batches(
        spark_session=spark_session,
        workspace=workspace,
        event_batches=[events],
        max_history_length=max_history_length,
        window_seconds=window_seconds,
        record_flatline=record_flatline,
    )[-1]


def _run_stateful_stream_batches(
    spark_session: SparkSession,
    workspace: Path,
    event_batches: list[list[Row]],
    max_history_length: int,
    window_seconds: float,
    record_flatline: bool = False,
) -> list[list[dict[str, float | int | None]]]:
    input_dir = workspace / "state_input"
    checkpoint_dir = workspace / "state_checkpoint"
    input_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    raw_schema = RawSensorData.get_spark_schema()
    raw_stream = spark_session.readStream.schema(raw_schema).parquet(str(input_dir))
    watermarked = raw_stream.withColumn(
        "event_time", F.to_timestamp(F.from_unixtime(F.col("timestamp")))
    ).withWatermark("event_time", "1 hour")

    def apply_state(
        key: tuple[int, int],
        pdf_iter: "iter[pd.DataFrame]",
        state: GroupState,
    ) -> "iter[pd.DataFrame]":
        if state.hasTimedOut:
            state.remove()
            payload = {
                "plant_id": key[0],
                "sensor_id": key[1],
                "last_value": None,
                "history_len": 0,
                "flatline_value": None,
                "flatline_timestamp": None,
            }
            return iter([pd.DataFrame([payload])])

        provider = SparkStateProvider(
            group_state=state,
            sensor_id=key[1],
            max_history_length=max_history_length,
        )
        readings: list[RawSensorData] = []
        for pdf in pdf_iter:
            if pdf.empty:
                continue
            for row in pdf.to_dict(orient="records"):
                row.pop("event_time", None)
                readings.append(RawSensorData(**row))

        readings.sort(key=lambda reading: reading.timestamp)
        for reading in readings:
            provider.update(reading.sensor_id, reading)

        last = provider.get_last_valid(key[1])
        if record_flatline and last is not None:
            provider.record_flatline(last.sensor_id, last.value, last.timestamp)
        flatline = provider.get_flatline(key[1])

        history = provider.get_recent_history(
            sensor_id=key[1],
            window_seconds=window_seconds,
            reference_timestamp=last.timestamp if last is not None else 0.0,
        )

        payload = {
            "plant_id": key[0],
            "sensor_id": key[1],
            "last_value": last.value if last is not None else None,
            "history_len": len(history),
            "flatline_value": flatline.value if flatline is not None else None,
            "flatline_timestamp": flatline.timestamp if flatline is not None else None,
        }
        return iter([pd.DataFrame([payload])])

    processed = watermarked.groupBy("plant_id", "sensor_id").applyInPandasWithState(
        apply_state,
        outputStructType=OUTPUT_SCHEMA,
        stateStructType=SensorState.get_spark_schema(),
        outputMode="update",
        timeoutConf=GroupStateTimeout.EventTimeTimeout,
    )

    query_name = "state_provider_results"
    query = (
        processed.writeStream.format("memory")
        .queryName(query_name)
        .outputMode("update")
        .option("checkpointLocation", str(checkpoint_dir))
        .start()
    )

    results: list[list[dict[str, float | int | None]]] = []
    try:
        for batch in event_batches:
            if batch:
                spark_session.createDataFrame(batch, raw_schema).write.mode("append").parquet(
                    str(input_dir)
                )
            query.processAllAvailable()
            rows = spark_session.sql(f"SELECT * FROM {query_name}").collect()
            results.append([row.asDict() for row in rows])
        return results
    finally:
        query.stop()
        try:
            spark_session.catalog.dropTempView(query_name)
        except Exception:
            pass


def test_state_provider_persists_last_valid_and_history(spark_session, tmp_path) -> None:
    """SparkStateProvider should persist last_valid and trim history."""
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        _make_event(
            plant_id=1,
            sensor_id=101,
            timestamp=(base_time.timestamp() + offset),
            value=20.0 + offset,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id=f"reading-{offset}",
        )
        for offset in (0, 10, 20)
    ]

    results = _run_stateful_stream(
        spark_session,
        tmp_path,
        events,
        max_history_length=2,
        window_seconds=3600,
    )

    assert len(results) == 1
    row = results[0]
    assert row["last_value"] == 40.0
    assert row["history_len"] == 2


def test_state_provider_trims_history_window(spark_session, tmp_path) -> None:
    """SparkStateProvider should trim history based on the requested window."""
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        _make_event(
            plant_id=1,
            sensor_id=202,
            timestamp=(base_time.timestamp() + offset),
            value=10.0 + offset,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id=f"reading-{offset}",
        )
        for offset in (0, 120)
    ]

    results = _run_stateful_stream(
        spark_session,
        tmp_path,
        events,
        max_history_length=5,
        window_seconds=30,
    )

    assert len(results) == 1
    row = results[0]
    assert row["last_value"] == 130.0
    assert row["history_len"] == 1


def test_state_provider_records_flatline_metadata(spark_session, tmp_path) -> None:
    """SparkStateProvider should persist flatline metadata in state."""
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        _make_event(
            plant_id=1,
            sensor_id=303,
            timestamp=base_time.timestamp(),
            value=18.5,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="reading-0",
        )
    ]

    results = _run_stateful_stream(
        spark_session,
        tmp_path,
        events,
        max_history_length=5,
        window_seconds=60,
        record_flatline=True,
    )

    assert len(results) == 1
    row = results[0]
    assert row["flatline_value"] == 18.5
    assert row["flatline_timestamp"] == pytest.approx(base_time.timestamp())


@pytest.mark.parametrize(
    ("max_history_length", "expected_length"),
    [(0, 0), (1, 1)],
)
def test_state_provider_history_cap_edges(
    spark_session, tmp_path, max_history_length: int, expected_length: int
) -> None:
    """History should respect small max_history_length values."""
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        _make_event(
            plant_id=1,
            sensor_id=606,
            timestamp=base_time.timestamp() + offset,
            value=10.0 + offset,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id=f"reading-{offset}",
        )
        for offset in (0, 5, 10)
    ]

    results = _run_stateful_stream(
        spark_session,
        tmp_path,
        events,
        max_history_length=max_history_length,
        window_seconds=3600,
    )

    row = results[0]
    assert row["last_value"] == 20.0
    assert row["history_len"] == expected_length


def test_state_provider_includes_window_boundary(spark_session, tmp_path) -> None:
    """Events exactly on the window boundary should be retained."""
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        _make_event(
            plant_id=1,
            sensor_id=707,
            timestamp=base_time.timestamp(),
            value=5.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="reading-0",
        ),
        _make_event(
            plant_id=1,
            sensor_id=707,
            timestamp=base_time.timestamp() + 10,
            value=6.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="reading-10",
        ),
    ]

    results = _run_stateful_stream(
        spark_session,
        tmp_path,
        events,
        max_history_length=5,
        window_seconds=10,
    )

    row = results[0]
    assert row["history_len"] == 2
    assert row["last_value"] == 6.0




def test_state_provider_overwrites_flatline_record() -> None:
    """Flatline metadata should be replaced by the latest record."""
    state = SensorState()
    state.record_flatline(value=1.0, timestamp=100.0)
    state.record_flatline(value=2.0, timestamp=200.0)

    assert state.flatline.value == 2.0
    assert state.flatline.timestamp == 200.0


def test_state_provider_first_reading_history_contains_current(spark_session, tmp_path) -> None:
    """The first reading should appear in recent history."""
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        _make_event(
            plant_id=1,
            sensor_id=911,
            timestamp=base_time.timestamp(),
            value=9.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="reading-0",
        )
    ]

    results = _run_stateful_stream(
        spark_session,
        tmp_path,
        events,
        max_history_length=5,
        window_seconds=3600,
    )

    row = results[0]
    assert row["last_value"] == 9.0
    assert row["history_len"] == 1
