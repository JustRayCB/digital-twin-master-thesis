from collections.abc import Iterable, Iterator

import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.streaming.state import GroupState, GroupStateTimeout

from dt.communication.dataclasses.preprocessing_config import (
    SensorConfig, SensorValidationConfig)
from dt.communication.dataclasses.processed_sensor_data import (
    ProcessedSensorData, ValidationFlag)
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.dataclasses.state import SensorState
from dt.communication.db_client import DatabaseApiClient
from dt.communication.topics import Topics
from dt.data.preprocess import validators
from dt.data.preprocess.dq import compute_dq_score
from dt.data.preprocess.imputers import (ImputationStrategy,
                                         build_imputation_strategy)
from dt.data.preprocess.smoothing import (SmoothingStrategy,
                                          build_smoothing_strategy)
from dt.data.preprocess.state import SparkStateProvider, StateProvider
from dt.utils import get_logger
from dt.utils.exceptions.drop_reading import DropReadingException

logger = get_logger(__name__)


PROCESSED_EVENT_COLUMNS = tuple(
    field.name for field in ProcessedSensorData.get_spark_schema().fields
)

ProcessedRecord = dict[str, object]
FlagStatus = dict[ValidationFlag, bool]

STATE_TIMEOUT_SECONDS = 30 * 60
WATERMARK_INTERVAL = "30 minutes"

# Caches for imputation and smoothing strategies to avoid redundant instantiation every Microbatch
# WARNING: These are global variables shared across Spark executors!
#           If the strategy implementations maintain internal state (wich currently don't as entirely dependent on StateProvider),
#           this may lead to unexpected behavior.
#           If we would happen to need per-executor stateful strategies in the future, we should move these caches
#           into the SparkStateProvider.
# NOTE: If the Strategy is changed during runtime (e.g. config update), the old instance will remain in the cache.
#       This can be mitigated by restarting the Spark job after config changes.
_global_imputation_cache: dict[str, ImputationStrategy] = {}
_global_smoothing_cache: dict[str, SmoothingStrategy] = {}


def _load_sensor_registry(rules: SensorValidationConfig) -> dict[int, str]:
    """Build a mapping of sensor IDs to config keys based on database descriptors.

    Parameters
    ----------
    rules : SensorValidationConfig
        Loaded preprocessing configuration containing known sensors.

    Returns
    -------
    dict[int, str]
        Mapping from sensor identifier to the configuration key it should use.
    """
    try:
        descriptors = DatabaseApiClient().list_sensors()
    except Exception as exc:
        logger.warning(f"Unable to load sensor registry from database: {exc}")
        return {}

    registry: dict[int, str] = {}
    for descriptor in descriptors:
        config_key = descriptor.name
        if config_key in rules.sensors:
            registry[descriptor.sensor_id] = config_key
    return registry


def _resolve_sensor_config(
    rules: SensorValidationConfig,
    plant_id: int,
    sensor_id: int,
    topic: Topics,
    sensor_registry: dict[int, str],
) -> tuple[str, SensorConfig]:
    """Resolve the sensor configuration from registry metadata.

    Parameters
    ----------
    rules : SensorValidationConfig
        Full preprocessing configuration.
    plant_id : int
        Identifier of the greenhouse plant owning the sensor.
    sensor_id : int
        Numeric sensor identifier looked up in the registry.
    topic : Topics
        Kafka topic associated with the reading.
    sensor_registry : dict[int, str]
        Mapping from sensor identifiers to configuration keys.

    Returns
    -------
    tuple[str, SensorConfig]
        Pair of the config key and the associated :class:`SensorConfig`.

    Raises
    ------
    KeyError
        Raised when the registry lacks an entry or the config key is undefined.
    """
    sensors = rules.sensors
    registry_key = sensor_registry.get(sensor_id)
    if registry_key is None:
        raise KeyError(
            f"No sensor registry entry for sensor_id={sensor_id} "
            f"(plant_id={plant_id}, topic={topic.value})"
        )
    try:
        return registry_key, sensors[registry_key]
    except KeyError as exc:
        raise KeyError(
            f"Sensor registry maps sensor_id={sensor_id} to '{registry_key}', "
            "but configuration does not define that sensor."
        ) from exc


def _initial_flags() -> FlagStatus:
    """Construct a flag mapping with all validation results marked as passing."""
    return {flag: False for flag in ValidationFlag}


def _get_imputation(
    cache: dict[str, ImputationStrategy],
    sensor_key: str,
    sensor_config: SensorConfig,
) -> ImputationStrategy:
    """Fetch or build the imputation strategy for the sensor.

    Parameters
    ----------
    cache : dict[str, ImputationStrategy]
        Strategy cache keyed by sensor config identifier.
    sensor_key : str
        Registry key associated with the sensor.
    sensor_config : SensorConfig
        Sensor configuration describing imputation preferences.

    Returns
    -------
    ImputationStrategy
        Strategy instance ready to compute imputed values.
    """
    imputation = cache.get(sensor_key)
    if imputation is None:
        imputation = build_imputation_strategy(sensor_config)
        cache[sensor_key] = imputation
    return imputation


def _get_smoothing(
    cache: dict[str, SmoothingStrategy],
    sensor_key: str,
    sensor_config: SensorConfig,
) -> SmoothingStrategy:
    """Fetch or build the smoothing strategy for the sensor.

    Parameters
    ----------
    cache : dict[str, SmoothingStrategy]
        Smoothing strategy cache keyed by sensor config identifier.
    sensor_key : str
        Registry key associated with the sensor.
    sensor_config : SensorConfig
        Sensor configuration describing smoothing preferences.

    Returns
    -------
    SmoothingStrategy
        Strategy instance ready to smooth processed readings.
    """
    smoothing = cache.get(sensor_key)
    if smoothing is None:
        smoothing = build_smoothing_strategy(sensor_config)
        cache[sensor_key] = smoothing
    return smoothing


def _run_validations(
    reading: RawSensorData,
    sensor_config: SensorConfig,
    state_provider: StateProvider,
) -> FlagStatus:
    """Execute validation checks and return triggered flags.

    Parameters
    ----------
    reading : RawSensorData
        Current raw sensor reading.
    sensor_config : SensorConfig
        Configuration specifying thresholds for the sensor.
    state_provider : StateProvider
        State bridge supplying historical context.

    Returns
    -------
    dict[ValidationFlag, bool]
        Mapping with violations marked ``True`` and passes marked ``False``.
    """
    flags = _initial_flags()

    is_range_ok, range_flag = validators.check_range(reading=reading, rule=sensor_config.range)
    if not is_range_ok:
        flags[range_flag] = True
        logger.info(
            f"Range validation failed for sensor_id={reading.sensor_id} "
            f"value={reading.value} range_check={sensor_config.range} ",
        )
        return flags

    previous_valid = state_provider.get_last_valid(reading.sensor_id)
    is_roc_ok, roc_flag = validators.check_rate_of_change(
        reading=reading,
        previous_valid=previous_valid,
        rule=sensor_config.roc,
    )
    if not is_roc_ok:
        flags[roc_flag] = True
        logger.info(
            f"Rate-of-change validation failed for sensor_id={reading.sensor_id} "
            f"value={reading.value} last_valid={previous_valid} roc_check={sensor_config.roc} ",
        )
        return flags

    history = list(
        state_provider.get_recent_history(
            sensor_id=reading.sensor_id,
            window_seconds=float(sensor_config.stuck.max_flat_seconds),
            reference_timestamp=float(reading.timestamp),
        )
    )
    history.append(reading)

    is_stuck_ok, stuck_flag = validators.check_stuck(
        history=history,
        rule=sensor_config.stuck,
    )
    if not is_stuck_ok:
        flags[stuck_flag] = True
        logger.info(
            f"Stuck-value validation failed for sensor_id={reading.sensor_id} "
            f"value={reading.value} stuck_check={sensor_config.stuck} ",
        )
        state_provider.record_flatline(
            sensor_id=reading.sensor_id,
            value=float(reading.value),
            timestamp=float(reading.timestamp),
        )

    return flags


def _compute_output_value(
    reading: RawSensorData,
    flags: FlagStatus,
    imputation: ImputationStrategy,
    smoothing: SmoothingStrategy,
    state_provider: StateProvider,
) -> tuple[float, bool, bool]:
    """Determine the output value after imputation and smoothing.

    Parameters
    ----------
    reading : RawSensorData
        Current raw sensor reading.
    flags : dict[ValidationFlag, bool]
        Validation results for the reading.
    imputation: ImputationStrategy
        Imputation strategy selected for the sensor.
    smoothing : SmoothingStrategy
        Smoothing strategy selected for the sensor.
    state_provider : StateProvider
        State bridge supplying historical context.

    Returns
    -------
    tuple[float, bool, bool]
        Triplet of the final numeric value, whether it was imputed, and whether
        any violation occurred.
    """
    violation = any(flags.values())
    value = float(reading.value)
    imputed = False

    if violation:
        imputed_value = imputation.compute(
            sensor_id=reading.sensor_id,
            reading=reading,
            state=state_provider,
        )
        if imputed_value is not None:
            value = float(imputed_value)
            imputed = True
        else:
            raise DropReadingException(
                f"Imputation failed for sensor_id={reading.sensor_id} "
                f"at timestamp={reading.timestamp}; dropping reading."
            )

    smoothed_value = smoothing.apply(
        sensor_id=reading.sensor_id,
        value=value,
        timestamp=float(reading.timestamp),
        state=state_provider,
    )
    return float(smoothed_value), imputed, violation


def _persist_valid_reading(
    reading: RawSensorData,
    state_provider: StateProvider,
) -> None:
    """Persist the provided value as the most recent valid reading.

    Parameters
    ----------
    reading : RawSensorData
        Original raw sensor reading.
    value : float
        Value that passed all validation checks.
    state_provider : StateProvider
        State bridge responsible for persisting sensor history.
    """
    state_provider.update(sensor_id=reading.sensor_id, reading=reading)


def _build_processed_record(
    reading: RawSensorData,
    value: float,
    flags: FlagStatus,
    dq_score: float,
    imputed: bool,
) -> ProcessedRecord:
    """Assemble the processed record ready for downstream publishing.

    Parameters
    ----------
    reading : RawSensorData
        Source reading that was evaluated.
    value : float
        Final value after imputation and smoothing.
    flags : dict[ValidationFlag, bool]
        Validation results for the reading.
    dq_score : float
        Calculated data-quality score.
    imputed : bool
        Indicates whether imputation took place.

    Returns
    -------
    dict[str, object]
        Dictionary matching :data:`PROCESSED_EVENT_SCHEMA`.
    """
    processed_data = ProcessedSensorData.from_raw_sensor_data(
        raw_data=reading,
        proc_value=value,
        flags=flags,
        dq_score=dq_score,
        imputed=imputed,
    )
    return processed_data.to_dict()


def _collect_readings(pdf_iter: Iterator[pd.DataFrame]) -> list[RawSensorData]:
    """Materialise RawSensorData instances from a Pandas iterator.

    Parameters
    ----------
    pdf_iter : Iterator[pandas.DataFrame]
        Iterator of Pandas DataFrames provided by Spark.

    Returns
    -------
    list[RawSensorData]
        Flattened list of raw readings extracted from the frames.
    """
    readings: list[RawSensorData] = []
    for pdf in pdf_iter:
        readings.extend(RawSensorData.from_row(row) for row in pdf.itertuples(index=False))
    return readings


def _extract_sensor_id(key: tuple) -> int:
    """Extract the numeric sensor identifier from a Spark group key."""
    return int(key[1]) if len(key) > 1 else int(key[0])


def _broadcast_pipeline_configs(
    spark_session: SparkSession,
    rules: SensorValidationConfig,
    weights: dict[str, float],
    sensor_registry: dict[int, str],
):
    """Broadcast static pipeline configuration across Spark executors.

    Parameters
    ----------
    spark_session : pyspark.sql.SparkSession
        Active Spark session managing the job.
    rules : SensorValidationConfig
        Loaded preprocessing configuration.
    weights : dict[str, float]
        Validation weights derived from ``rules``.
    sensor_registry : dict[int, str]
        Mapping from sensor identifier to configuration key.

    Returns
    -------
    tuple
        Broadcasted copies of ``rules``, ``weights``, and ``sensor_registry``.
    """
    sc = spark_session.sparkContext
    return (
        sc.broadcast(rules),
        sc.broadcast(weights),
        sc.broadcast(sensor_registry),
    )


def _process_readings(
    readings: Iterable[RawSensorData],
    state_provider: StateProvider,
    rules: SensorValidationConfig,
    weights: dict[str, float],
    sensor_registry: dict[int, str],
    watermark_seconds: float | None,
) -> tuple[list[ProcessedRecord], float | None]:
    """Process a batch of readings for a specific sensor group.

    Parameters
    ----------
    readings : Iterable[RawSensorData]
        Raw sensor readings for the current group key.
    state_provider : StateProvider
        State implementation tracking historical context.
    rules : SensorValidationConfig
        Full preprocessing configuration.
    weights : dict[str, float]
        Validation weights applied to DQ scoring.
    sensor_registry : dict[int, str]
        Registry connecting sensor identifiers with configuration keys.
    watermark_seconds : float or None
        Current event-time watermark expressed in epoch seconds.

    Returns
    -------
    tuple[list[dict[str, object]], float or None]
        Collection of processed records ready for downstream sinks and the
        maximum timestamp encountered while processing.
    """
    sorted_readings = sorted(readings, key=lambda item: item.timestamp)
    if not sorted_readings:
        return [], None

    records: list[ProcessedRecord] = []
    latest_timestamp: float | None = None

    for reading in sorted_readings:
        flags = _initial_flags()
        late_event = False

        try:
            sensor_key, sensor_config = _resolve_sensor_config(
                rules,
                plant_id=reading.plant_id,
                sensor_id=reading.sensor_id,
                topic=reading.topic,
                sensor_registry=sensor_registry,
            )
        except KeyError:
            logger.warning(
                f"Unknown sensor encountered: plant_id={reading.plant_id} "
                f"sensor_id={reading.sensor_id} topic={reading.topic}",
            )
            continue

        previous_valid = state_provider.get_last_valid(reading.sensor_id)
        # If the reading is older than the watermark
        if watermark_seconds is not None and float(reading.timestamp) < watermark_seconds:
            late_event = True
            logger.info(
                f"Late event detected (before watermark): plant_id={reading.plant_id} "
                f"sensor_id={reading.sensor_id} event_ts={reading.timestamp} watermark={watermark_seconds} "
                f"correlation_id={reading.correlation_id}",
            )
        # Or if it's older than the last valid reading we have stored
        elif previous_valid is not None and float(reading.timestamp) < float(
            previous_valid.timestamp
        ):
            late_event = True
            logger.info(
                f"Late event detected (older than last valid): plant_id={reading.plant_id} "
                f"sensor_id={reading.sensor_id} event_ts={reading.timestamp} "
                f"last_valid_ts={previous_valid.timestamp} correlation_id={reading.correlation_id}",
            )

        strategy = _get_imputation(_global_imputation_cache, sensor_key, sensor_config)
        smoothing = _get_smoothing(_global_smoothing_cache, sensor_key, sensor_config)

        flags.update(
            _run_validations(
                reading=reading,
                sensor_config=sensor_config,
                state_provider=state_provider,
            )
        )

        # Compute final value after imputation (if needed) and smoothing
        try:
            value, imputed, violation = _compute_output_value(
                reading=reading,
                flags=flags,
                imputation=strategy,
                smoothing=smoothing,
                state_provider=state_provider,
            )
        except DropReadingException as exc:
            logger.warning(str(exc))
            # We set the reading as invalid and assign a DQ score of 0.0
            flags[ValidationFlag.VALID] = False
            dq_score = 0.0
            records.append(
                _build_processed_record(
                    reading=reading,
                    value=float(reading.value),
                    flags=flags,
                    dq_score=dq_score,
                    imputed=False,
                )
            )
            base_ts = latest_timestamp if latest_timestamp is not None else float(reading.timestamp)
            latest_timestamp = max(base_ts, float(reading.timestamp))
            continue

        if not violation and not late_event:
            # We persist only valid readings, not the one we imputed or smoothed
            # in order not to hide any jump with our "invented" values.
            _persist_valid_reading(reading=reading, state_provider=state_provider)

        flags[ValidationFlag.VALID] = not violation

        dq_score = compute_dq_score(flags=flags, weights=weights)
        records.append(
            _build_processed_record(
                reading=reading,
                value=value,
                flags=flags,
                dq_score=dq_score,
                imputed=imputed,
            )
        )
        base_ts = latest_timestamp if latest_timestamp is not None else float(reading.timestamp)
        latest_timestamp = max(base_ts, float(reading.timestamp))

    return records, latest_timestamp


def _stream_group_processor(
    key: tuple,
    pdf_iter: Iterator[pd.DataFrame],
    group_state: GroupState,
    rules: SensorValidationConfig,
    weights: dict[str, float],
    sensor_registry: dict[int, str],
) -> Iterator[pd.DataFrame]:
    """Spark-compatible function processing grouped sensor readings.

    Parameters
    ----------
    key : tuple
        Spark grouping key containing plant and sensor identifiers.
    pdf_iter : Iterator[pandas.DataFrame]
        Iterator over Pandas batches in the group.
    group_state : pyspark.sql.streaming.state.GroupState
        Spark state handle for the group.
    rules : SensorValidationConfig
        Broadcast preprocessing configuration.
    weights : dict[str, float]
        Validation weights.
    sensor_registry : dict[int, str]
        Broadcast sensor registry mapping.

    Returns
    -------
    Iterator[pandas.DataFrame]
        Iterator yielding zero or one processed Pandas DataFrame.
    """
    if group_state.hasTimedOut:
        logger.info(f"State timeout for sensor group {key}; removing state.")
        group_state.remove()
        return iter(())

    sensor_id = _extract_sensor_id(key)
    state_provider = SparkStateProvider(group_state=group_state, sensor_id=sensor_id)

    readings = _collect_readings(pdf_iter)

    # Obtain the current watermark in seconds since epoch
    # The watermark will be used to identify late events
    watermark_ms = group_state.getCurrentWatermarkMs()
    watermark_seconds = watermark_ms / 1000.0

    records, latest_timestamp = _process_readings(
        readings, state_provider, rules, weights, sensor_registry, watermark_seconds
    )
    if not records:
        return iter(())

    if latest_timestamp is not None:
        timeout_ms = int((latest_timestamp + STATE_TIMEOUT_SECONDS) * 1000.0)
        # Set the timeout timestamp for the group state
        # If no new data arrives by then, the state will be removed
        group_state.setTimeoutTimestamp(timeout_ms)

    processed_pdf = pd.DataFrame.from_records(records, columns=PROCESSED_EVENT_COLUMNS)
    return iter([processed_pdf])


def build_preprocessing_stream(
    spark_session: SparkSession, raw_events: DataFrame, config_path: str
) -> DataFrame:
    """Construct the preprocessing streaming pipeline.

    Parameters
    ----------
    spark_session : pyspark.sql.SparkSession
        Active Spark session used to run the job.
    raw_events : pyspark.sql.DataFrame
        Streaming DataFrame sourced from Kafka containing raw sensor events.
    config_path : str
        File system path to the preprocessing configuration YAML file.

    Returns
    -------
    pyspark.sql.DataFrame
        Streaming DataFrame containing processed events ready for Kafka sink.

    Raises
    ------
    ValueError
        Raised when ``raw_events`` is not a streaming DataFrame.
    """
    if not raw_events.isStreaming:
        raise ValueError("build_preprocessing_stream requires a streaming DataFrame input.")

    rules = SensorValidationConfig.load(config_path)
    weights = rules.defaults.scoring.weights.to_dict()
    sensor_registry = _load_sensor_registry(rules)

    (
        rules_broadcast,
        weights_broadcast,
        registry_broadcast,
    ) = _broadcast_pipeline_configs(spark_session, rules, weights, sensor_registry)

    def _stateful_func(
        key: tuple,
        pdf_iter: Iterator[pd.DataFrame],
        state: GroupState,
    ) -> Iterator[pd.DataFrame]:
        """Delegate to :func:`_stream_group_processor` within Spark's callback."""
        return _stream_group_processor(
            key,
            pdf_iter,
            state,
            rules_broadcast.value,
            weights_broadcast.value,
            registry_broadcast.value,
        )

    # Use event-time watermarking to handle late-arriving data and be able to expire state
    events_with_time = raw_events.withColumn(
        "event_time", F.to_timestamp(F.from_unixtime(F.col("timestamp")))
    )  # our column 'timestamp' is in seconds since epoch but Spark expects a TimestampType
    watermarked = events_with_time.withWatermark("event_time", WATERMARK_INTERVAL)

    return watermarked.groupBy("plant_id", "sensor_id").applyInPandasWithState(
        _stateful_func,  # pyright: ignore[]
        outputStructType=ProcessedSensorData.get_spark_schema(),
        stateStructType=SensorState.get_spark_schema(),
        outputMode="update",
        timeoutConf=GroupStateTimeout.EventTimeTimeout,
    )
