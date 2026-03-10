from dt.data.preprocess.core.context import ProcessingContext
from dt.data.preprocess.stages.base import BaseProcessor
from dt.utils import get_logger

logger = get_logger(__name__)


class SmoothingProcessor(BaseProcessor):
    """Applies smoothing filters to reduce noise in sensor readings.

    Uses configured smoothing strategies (pass-through, EWMA, etc.) to filter
    noise from sensor data. If the reading was imputed, smooths the imputed value;
    otherwise smooths the calibrated value.

    Parameters
    ----------
    config_manager : ConfigurationManager
        Configuration manager providing smoothing strategies.
    """

    def __init__(self, config_manager) -> None:
        """Initialize the smoothing processor.

        Parameters
        ----------
        config_manager : ConfigurationManager
            Configuration manager for strategy resolution.
        """
        self._config_manager = config_manager

    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Apply smoothing to the reading value.

        Parameters
        ----------
        context : ProcessingContext
            Current processing context with calibrated_reading and imputation status set.

        Returns
        -------
        ProcessingContext
            Updated context with smoothed_value set.
        """
        reading = context.calibrated_reading
        if reading is None:
            raise ValueError("SmoothingProcessor requires calibrated_reading to be set")

        sensor_config = context.sensor_config
        sensor_key = context.sensor_key
        sensor_id = reading.sensor_id
        state_provider = context.state_provider

        # Determine which value to smooth
        value_to_smooth = context.get_final_value()

        # Get smoothing strategy
        if sensor_config is None or sensor_key is None:
            raise ValueError("SmoothingProcessor requires sensor_config and sensor_key to be set")
        strategy = self._config_manager.get_smoothing_strategy(sensor_key, reading.topic)

        # Apply smoothing
        smoothed_value = strategy.apply(
            sensor_id=sensor_id,
            value=float(value_to_smooth),
            timestamp=float(reading.timestamp),
            state=state_provider,
        )

        context.smoothed_value = float(smoothed_value)

        logger.debug(
            f"Smoothed sensor_id={sensor_id}: {value_to_smooth} -> {smoothed_value} "
            f"(strategy={strategy.__class__.__name__})"
        )

        return context
