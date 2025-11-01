from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from dt.communication.dataclasses.processed_sensor_data import ProcessedSensorData
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess.configuration.manager import ConfigurationManager
from dt.data.preprocess.spark_adapter import SparkStreamingAdapter
from dt.utils import Config, get_logger

logger = get_logger(__name__)

RAW_TOPIC_PATTERN = (
    ".".join(Topics.TEMPERATURE.raw.split(".")[:-1]) + ".*"
)  # Subscribe to all raw sensor topics


def _build_topic_map() -> dict[str, str]:
    """Map sensor base topics to their processed Kafka equivalents."""
    mapping: dict[str, str] = {}
    for topic in Topics.list_sensor_topics():
        mapping[topic] = topic.processed
    return mapping


def _build_spark_session() -> SparkSession:
    """Initialise a Spark session with reasonable defaults."""
    session = SparkSession.builder.appName(Config.SPARK_APP_NAME).getOrCreate()
    session.sparkContext.setLogLevel(Config.SPARK_LOG_LEVEL)
    return session


def _read_raw_events(
    spark: SparkSession,
    kafka_bootstrap: str,
    topic_pattern: str,
    starting_offsets: str,
) -> DataFrame:
    """Stream raw sensor events from Kafka and project them onto the dataclass schema."""
    schema = RawSensorData.get_spark_schema()
    kafka_stream = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", kafka_bootstrap)
        .option("subscribePattern", topic_pattern)
        .option("startingOffsets", starting_offsets)
        .option("failOnDataLoss", "false")
        .load()
    )
    payload = kafka_stream.selectExpr("CAST(value AS STRING) AS payload")
    parsed = payload.select(F.from_json("payload", schema).alias("data"))
    return parsed.select("data.*")


def _prepare_kafka_sink(processed_events: DataFrame, topic_map: dict[str, str]) -> DataFrame:
    """Transform processed events into a Kafka-compatible DataFrame."""
    # Create a mapping from base topics to processed topics
    mapping_literals: list = []
    for raw_topic, processed_topic in topic_map.items():
        mapping_literals.append(F.lit(raw_topic))
        mapping_literals.append(F.lit(processed_topic))
    topic_mapping = F.create_map(*mapping_literals)
    # Rename the original topic column to avoid conflicts (will be used in the payload)
    df = processed_events.withColumnRenamed("topic", "base_topic")
    # Add the new topic column based on the mapping (the base topic is the key and will give the processed topic)
    df = df.withColumn("topic", topic_mapping.getItem(F.col("base_topic")))

    # Build the payload as a JSON string
    payload_columns = []
    for field in ProcessedSensorData.get_spark_schema().fieldNames():  # Taken in order
        if field == "topic":
            # Use the original base topic in the payload (not raw and not processed)
            payload_columns.append(F.col("base_topic").alias("topic"))
        else:  # Other fields are taken directly
            payload_columns.append(F.col(field))

    # Construct the payload struct and convert to JSON
    payload_struct = F.struct(*payload_columns)
    return df.select(
        F.col("topic"),  # Processed topic computed earlier from mapping
        F.to_json(payload_struct).alias("value"),  # JSON payload
    )


def main() -> None:
    """Execute the preprocessing streaming pipeline."""
    config_path = Config.PREPROCESSING_CONFIG_PATH
    checkpoint_dir = Config.PREPROCESSING_CHECKPOINT_DIR
    kafka_bootstrap = Config.KAFKA_URL

    logger.info("Starting preprocessing pipeline (modular architecture).")
    spark = _build_spark_session()

    try:
        config_manager = ConfigurationManager(config_path)
        adapter = SparkStreamingAdapter(config_manager)

        raw_events = _read_raw_events(
            spark,
            kafka_bootstrap=kafka_bootstrap,
            topic_pattern=RAW_TOPIC_PATTERN,
            starting_offsets=Config.SPARK_STARTING_OFFSETS,
        )

        processed_stream = adapter.build_preprocessing_stream(spark, raw_events)
        kafka_ready = _prepare_kafka_sink(processed_stream, _build_topic_map())
        query = (
            kafka_ready.writeStream.format("kafka")
            .option("kafka.bootstrap.servers", kafka_bootstrap)
            .option("checkpointLocation", checkpoint_dir)
            .outputMode("update")
            .start()
        )
        query.awaitTermination()
    except KeyboardInterrupt:
        logger.info("Stopping preprocessing pipeline (interrupt).")
    finally:
        for stream in list(spark.streams.active):
            try:
                stream.stop()
            except Exception:
                logger.warning("Unable to stop stream cleanly", exc_info=True)
        spark.stop()


if __name__ == "__main__":
    main()
