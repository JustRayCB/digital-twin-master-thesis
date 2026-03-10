from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.core.context import ProcessingContext
from dt.data.preprocess.core.state import StateProvider
from dt.data.preprocess.stages.base import BaseProcessor
from dt.data.preprocess.stages.validation.checks import (check_range,
                                                         check_rate_of_change,
                                                         check_stuck)
from dt.data.preprocess.stages.validation.scoring import compute_dq_score
from dt.utils import get_logger

logger = get_logger(__name__)


class ValidationProcessor(BaseProcessor):
    """Validates sensor readings against configured rules.

    Performs three validation checks:
    1. Range check: Value within min/max bounds
    2. Rate-of-change check: Value doesn't change too quickly
    3. Stuck check: Sensor isn't flatlined

    Parameters
    ----------
    config_manager : ConfigurationManager
        Configuration manager providing DQ scoring weights.
    """

    def __init__(self, config_manager) -> None:
        """Initialize the validation processor.

        Parameters
        ----------
        config_manager : ConfigurationManager
            Configuration manager for DQ weights.
        """
        self._config_manager = config_manager

    def _check_late_event(
        self,
        reading: RawSensorData,
        state_provider: StateProvider,
        watermark_seconds: float | None,
    ) -> bool:
        """Check if reading is a late-arriving event."""
        reading_ts = float(reading.timestamp)

        if watermark_seconds and reading_ts < watermark_seconds:
            logger.info(
                f"Late event (watermark): sensor_id={reading.sensor_id} "
                f"timestamp={reading.timestamp} watermark={watermark_seconds}"
            )
            return True

        previous_valid = state_provider.get_last_valid(reading.sensor_id)
        if previous_valid and reading_ts < float(previous_valid.timestamp):
            logger.info(
                f"Late event (older than last valid): sensor_id={reading.sensor_id} "
                f"timestamp={reading.timestamp} last_valid={previous_valid.timestamp}"
            )
            return True

        return False

    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Validate the calibrated reading and compute data quality score.

        Parameters
        ----------
        context : ProcessingContext
            Current processing context with calibrated_reading set.

        Returns
        -------
        ProcessingContext
            Updated context with flags, is_valid, is_late_event, and dq_score set.
        """
        reading = context.calibrated_reading
        if reading is None:
            raise ValueError("ValidationProcessor requires calibrated_reading to be set")

        sensor_config = context.sensor_config
        sensor_id = reading.sensor_id
        state_provider = context.state_provider
        watermark_seconds = context.watermark_seconds

        if sensor_config is None:
            raise ValueError("ValidationProcessor requires sensor_config to be set")
        validation = sensor_config.validation
        if validation is None:
            raise ValueError("ValidationProcessor requires sensor_config.validation to be set")
        if validation.range is None or validation.roc is None or validation.stuck is None:
            raise ValueError(
                "ValidationProcessor requires validation range, roc, and stuck to be set"
            )

        # Run validation checks
        # NOTE: Flags use True = violation occurred, False = no violation

        # Check for late events
        context.is_late_event = self._check_late_event(reading, state_provider, watermark_seconds)

        # Range check
        range_passed, range_flag = check_range(reading, validation.range)
        if not range_passed:
            logger.info(
                f"Range validation failed: sensor_id={sensor_id} "
                f"value={reading.value} range=[{validation.range.min}, {validation.range.max}]"
            )
            context.mark_invalid_flag(range_flag)
            return self._finalize_context(context)

        # Rate of change check
        previous_valid = state_provider.get_last_valid(sensor_id)
        roc_passed, roc_flag = check_rate_of_change(reading, previous_valid, validation.roc)
        if not roc_passed:
            logger.info(
                f"Rate-of-change validation failed: sensor_id={sensor_id} "
                f"value={reading.value} prev_value={previous_valid.value if previous_valid else None}"
            )
            context.mark_invalid_flag(roc_flag)
            return self._finalize_context(context)

        # Stuck check - need history window
        if validation.stuck.enabled:
            history = list(
                state_provider.get_recent_history(
                    sensor_id=sensor_id,
                    window_seconds=validation.stuck.max_flat_seconds,
                    reference_timestamp=float(reading.timestamp),
                )
            )

            history.append(reading)
            stuck_passed, stuck_flag = check_stuck(history, validation.stuck)
            if not stuck_passed:
                logger.info(f"Stuck validation failed: sensor_id={sensor_id} value={reading.value}")
                context.mark_invalid_flag(stuck_flag)
                state_provider.record_flatline(
                    sensor_id=sensor_id,
                    value=float(reading.value),
                    timestamp=float(reading.timestamp),
                )

        # Calculate data quality score using existing function
        context = self._finalize_context(context)

        logger.debug(
            f"Validated sensor_id={sensor_id}: valid={context.is_valid}, dq_score={context.dq_score:.2f}, flags={context.flags}"
        )

        return context

    def _compute_dq_score(
        self,
        flags: dict[ValidationFlag, bool],
    ) -> float:
        """Compute data quality score based on validation flags.

        Parameters
        ----------
        flags : dict[ValidationFlag, bool]
            Validation flags indicating which checks failed.

        Returns
        -------
        float
            Computed data quality score.
        """
        weights = self._config_manager.get_dq_weights()
        return compute_dq_score(flags, weights)

    def _finalize_context(self, context: ProcessingContext) -> ProcessingContext:
        """Update context with computed data quality score before returning."""
        context.dq_score = self._compute_dq_score(context.flags)
        return context
