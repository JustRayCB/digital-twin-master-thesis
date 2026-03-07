from typing import Iterable, Iterator

import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.streaming.state import GroupState, GroupStateTimeout

from dt.communication.adapters import load
from dt.communication.dataclasses.processed_sensor_data import (
    ProcessedSensorData, ValidationFlag)
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.config.manager import ConfigurationManager
from dt.data.preprocess.core.context import ProcessingContext
from dt.data.preprocess.core.pipeline import PipelineBuilder
from dt.data.preprocess.core.state import SensorState, SparkStateProvider
from dt.utils import Config, get_logger
from dt.utils.exceptions.drop_reading import DropReadingException

logger = get_logger(__name__)

PROCESSED_EVENT_COLUMNS = tuple(
    field.name for field in ProcessedSensorData.get_spark_schema().fields
)


class SparkStreamingAdapter:
    """Adapter for integrating preprocessing pipeline with Spark Structured Streaming.

    This class handles all Spark-specific concerns:
    - Reading from Kafka
    - Applying watermarks
    - Managing stateful group processing
    - Writing to Kafka

    Parameters
    ----------
    spark_session : SparkSession
        Active Spark session.
    config_manager : ConfigurationManager
        Configuration manager for pipeline construction.
    """

    def __init__(self, config_manager: ConfigurationManager) -> None:
        """Initialize the Spark adapter.

        Parameters
        ----------
        config_manager : ConfigurationManager
            Configuration manager.
        """
        self._config_manager = config_manager
        self._pipeline_builder = PipelineBuilder(config_manager)

    def setup_watermark(self, raw_events: DataFrame, interval: str) -> DataFrame:
        """
        Set up event-time watermarking for late data handling.

        Parameters
        ----------
        raw_events : DataFrame
            Input streaming DataFrame with timestamp column (epoch seconds).
        interval : str
            Watermark delay threshold (e.g., "30 minutes").

        Returns
        -------
        DataFrame
            DataFrame with watermark configured on event_time column.

        Raises
        ------
        ValueError
            If raw_events is not a streaming DataFrame.
        """
        if not raw_events.isStreaming:
            raise ValueError("setup_watermark requires a streaming DataFrame input.")

        # Convert epoch seconds to TimestampType for watermarking
        events_with_time = raw_events.withColumn(
            "event_time", F.to_timestamp(F.from_unixtime(F.col("timestamp")))
        )
        # Apply watermark
        watermarked = events_with_time.withWatermark("event_time", interval)

        logger.info(f"Configured watermark with interval '{interval}' " f"on event_time column")
        return watermarked

    def build_preprocessing_stream(
        self, spark_session: SparkSession, raw_events: DataFrame
    ) -> DataFrame:
        """Build the full preprocessing streaming pipeline.

        Parameters
        ----------
        raw_events : DataFrame
            Streaming DataFrame of raw sensor events.

        Returns
        -------
        DataFrame
            Streaming DataFrame of processed sensor events.

        Raises
        ------
        ValueError
            When raw_events is not a streaming DataFrame.
        """
        if not raw_events.isStreaming:
            raise ValueError("build_preprocessing_stream requires a streaming DataFrame input.")

        logger.info("Broadcasting configurations to Spark executors...")
        sc = spark_session.sparkContext
        config_broadcast = sc.broadcast(self._config_manager)

        logger.info("Setting up event-time watermarking...")
        watermarked = self.setup_watermark(raw_events, Config.SPARK_WATERMARK_INTERVAL.value)

        def process_sensor_group(
            key: tuple,
            pdf_iter: Iterator[pd.DataFrame],
            state: GroupState,
        ) -> Iterator[pd.DataFrame]:
            return self._process_sensor_group_stateful(
                key=key,
                pdf_iter=pdf_iter,
                group_state=state,
                config_manager=config_broadcast.value,
            )

        logger.info("Applying stateful group processing...")
        processed_df = watermarked.groupBy("plant_id", "sensor_id").applyInPandasWithState(
            process_sensor_group,  # type: ignore[arg-type]
            outputStructType=ProcessedSensorData.get_spark_schema(),
            stateStructType=SensorState.get_spark_schema(),
            outputMode="update",
            timeoutConf=GroupStateTimeout.EventTimeTimeout,
        )
        logger.info("Preprocessing pipeline successfully configured")
        return processed_df

    def _process_sensor_group_stateful(
        self,
        key: tuple,
        pdf_iter: Iterator[pd.DataFrame],
        group_state: GroupState,
        config_manager: ConfigurationManager,
    ) -> Iterator[pd.DataFrame]:
        """Process a sensor group with Spark state management.

        Parameters
        ----------
        key : tuple
            Spark grouping key (plant_id, sensor_id).
        pdf_iter : Iterator[pd.DataFrame]
            Iterator over Pandas DataFrames in this microbatch.
        group_state : GroupState
            Spark state handle for the group.
        config_manager : ConfigurationManager
            Broadcasted configuration manager.

        Returns
        -------
        Iterator[pd.DataFrame]
            Iterator yielding zero or one processed DataFrame.
        """
        if group_state.hasTimedOut:
            logger.info(f"State timeout for sensor group {key}; removing state.")
            group_state.remove()
            return iter(())

        sensor_id = self._extract_sensor_id(key)
        state_provider = SparkStateProvider(group_state=group_state, sensor_id=sensor_id)

        # Collect readings from Pandas batches
        readings: list[RawSensorData] = self._collect_readings(pdf_iter)

        if not readings:  # No readings to process
            return iter(())

        # Get watermark
        watermark_ms = group_state.getCurrentWatermarkMs()
        watermark_seconds = watermark_ms / 1000.0 if watermark_ms >= 0 else None

        # Process all readings
        records, latest_timestamp = self._process_readings(
            readings=readings,
            state_provider=state_provider,
            watermark_seconds=watermark_seconds,
            config_manager=config_manager,
        )

        if latest_timestamp is not None:
            timeout_ms = int((latest_timestamp + int(Config.SPARK_STATE_TIMEOUT_SECONDS)) * 1000.0)
            group_state.setTimeoutTimestamp(timeout_ms)

        # Build output DataFrame
        return self.build_output_dataframe(records)

    def _process_readings(
        self,
        readings: Iterable[RawSensorData],
        state_provider: SparkStateProvider,
        watermark_seconds: float | None,
        config_manager: ConfigurationManager,
    ) -> tuple[list[dict], float | None]:
        """
        Process a batch of readings for a sensor group.

        Parameters
        ----------
        readings : Iterable[RawSensorData]
            Raw sensor readings to process.
        state_provider : SparkStateProvider
            State provider for historical context.
        watermark_seconds : Optional[float]
            Current watermark in epoch seconds.

        Returns
        -------
        tuple[list[dict], Optional[float]]
            Processed records and latest timestamp.
        """
        # Sort readings by timestamp
        sorted_readings = sorted(readings, key=lambda r: r.timestamp)

        records: list[dict] = []
        latest_timestamp: float | None = None

        pipeline = self._pipeline_builder.build_standard_pipeline()

        for reading in sorted_readings:
            try:
                # Resolve sensor configuration
                sensor_key, sensor_config = config_manager.resolve_sensor_config(
                    plant_id=reading.plant_id,
                    sensor_id=reading.sensor_id,
                    topic=reading.topic,
                )
            except KeyError:
                logger.warning(
                    f"Unknown sensor encountered: plant_id={reading.plant_id} "
                    f"sensor_id={reading.sensor_id} topic={reading.topic}"
                )
                continue

            # Create processing context
            context = ProcessingContext(
                reading=reading,
                state_provider=state_provider,
                watermark_seconds=watermark_seconds,
                sensor_key=sensor_key,
                sensor_config=sensor_config,
                calibration_profile_id=sensor_config.calibration_profile_id or "",
                normalization_profile_id=sensor_config.normalization_profile_id or "",
            )

            record_emitted = False
            try:
                # Execute pipeline
                result = pipeline.process(context)
            except DropReadingException as exc:
                logger.warning(
                    "Dropped reading for sensor_id=%s at timestamp=%s: %s",
                    reading.sensor_id,
                    reading.timestamp,
                    exc,
                )
                records.append(self._build_invalid_record(exc.context))
                record_emitted = True
            else:
                # Check if reading should be persisted as valid
                if result.is_valid and not result.is_late_event and result.calibrated_reading:
                    state_provider.update(
                        sensor_id=reading.sensor_id,
                        reading=result.calibrated_reading,
                    )
                records.append(result.to_dict())
                record_emitted = True

            # Track latest timestamp
            if record_emitted:
                reading_ts = float(reading.timestamp)
                base_ts = latest_timestamp if latest_timestamp is not None else reading_ts
                latest_timestamp = max(base_ts, reading_ts)

        return records, latest_timestamp

    def _build_invalid_record(self, context: ProcessingContext) -> dict:
        """Build a processed record for an invalid reading.

        Parameters
        ----------
        context : ProcessingContext
            Processing context associated with the dropped reading.

        Returns
        -------
        dict
            Processed record dictionary.
        """
        context.flags[ValidationFlag.VALID] = False
        context.is_valid = False
        context.dq_score = 0.0
        context.imputed = context.imputed
        if context.calibrated_reading is None:
            context.calibrated_reading = context.reading
        return context.to_dict()

    def _extract_sensor_id(self, key: tuple) -> int:
        """Extract sensor ID from Spark group key."""
        return int(key[1]) if len(key) > 1 else int(key[0])

    def _collect_readings(self, pdf_iter: Iterator[pd.DataFrame]) -> list[RawSensorData]:
        """
        Materialize RawSensorData instances from Pandas iterator.

        Parameters
        ----------
        pdf_iter : Iterator[pd.DataFrame]
            Iterator of Pandas DataFrames from Spark.

        Returns
        -------
        list[RawSensorData]
            List of raw sensor readings.
        """
        readings: list[RawSensorData] = []
        for pdf in pdf_iter:
            readings.extend(
                load("spark_row", RawSensorData, row) for row in pdf.itertuples(index=False)
            )
        return readings

    def build_output_dataframe(self, records: list[dict]) -> Iterator[pd.DataFrame]:
        """Build Spark DataFrame from processed records.

        Parameters
        ----------
        records : list[dict]
            List of processed sensor data records.

        Returns
        -------
        Iterator[pd.DataFrame]
            Iterator yielding single DataFrame.
        """
        if not records:
            return iter(())

        processed_pdf = pd.DataFrame.from_records(records)
        processed_pdf = processed_pdf.reindex(columns=PROCESSED_EVENT_COLUMNS)
        return iter([processed_pdf])
