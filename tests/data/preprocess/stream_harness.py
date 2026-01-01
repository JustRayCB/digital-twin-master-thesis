import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from pyspark.sql import DataFrame, Row, SparkSession

from dt.communication.adapters import load
from dt.communication.dataclasses import SensorDescriptor
from dt.communication.dataclasses.processed_sensor_data import ProcessedSensorData
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess.config.manager import ConfigurationManager
from dt.data.preprocess.spark_adapter import SparkStreamingAdapter

DEFAULT_TEMPLATE_KEY = "greenhouse.temperature.defaults"


def register_sensors(sensor_registry: dict[str, Any], names: list[str]) -> dict[str, SensorDescriptor]:
    """Register sensors in the Timescale-backed database service for tests."""
    register = sensor_registry["register"]
    return {name: register(name) for name in names}


def write_config(workspace: Path, config: dict[str, Any]) -> str:
    """Persist the provided preprocessing configuration to disk."""
    config_path = workspace / "preprocess_config.yml"
    config_path.write_text(yaml.safe_dump(config))
    return str(config_path)


def make_event(
    plant_id: int,
    sensor_id: int,
    timestamp: float,
    value: float,
    unit: str,
    topic: Topics,
    correlation_id: str,
) -> Row:
    """Create a Spark Row compatible with RawSensorData.get_spark_schema()."""
    return Row(
        plant_id=int(plant_id),
        sensor_id=int(sensor_id),
        timestamp=float(timestamp),
        value=float(value),
        unit=unit,
        topic=topic.value,
        correlation_id=correlation_id,
    )


def run_pipeline(
    spark: SparkSession,
    workspace: Path,
    config_path: str,
    events: list[Row],
) -> list[ProcessedSensorData]:
    """Execute the preprocessing stream against a fixed batch of events."""
    input_dir = workspace / f"stream_input_{uuid4().hex}"
    checkpoint = workspace / f"chk_{uuid4().hex}"
    input_dir.mkdir(parents=True, exist_ok=True)
    checkpoint.mkdir(parents=True, exist_ok=True)

    raw_schema = RawSensorData.get_spark_schema()
    spark.createDataFrame(events, raw_schema).write.mode("overwrite").format("parquet").save(
        str(input_dir)
    )
    raw_stream = spark.readStream.format("parquet").schema(raw_schema).load(str(input_dir))

    config_manager = ConfigurationManager(config_path)
    adapter = SparkStreamingAdapter(config_manager)
    processed_stream: DataFrame = adapter.build_preprocessing_stream(spark, raw_stream)

    query_name = f"processed_{uuid4().hex}"
    query = (
        processed_stream.writeStream.format("memory")
        .queryName(query_name)
        .outputMode("update")
        .option("checkpointLocation", str(checkpoint))
        .start()
    )

    try:
        query.processAllAvailable()
        rows = spark.sql(f"SELECT * FROM {query_name}").collect()
        return [load("spark_row", ProcessedSensorData, row) for row in rows]
    finally:
        query.stop()
        try:
            spark.catalog.dropTempView(query_name)
        except Exception:
            pass
        shutil.rmtree(checkpoint, ignore_errors=True)
        shutil.rmtree(input_dir, ignore_errors=True)

