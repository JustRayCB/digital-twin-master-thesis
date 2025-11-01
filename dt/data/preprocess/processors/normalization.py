from dt.data.preprocess.configuration.manager import ConfigurationManager
from dt.data.preprocess.pipeline.context import ProcessingContext
from dt.data.preprocess.processors.base import BaseProcessor
from dt.utils import get_logger

logger = get_logger(__name__)


class NormalizationProcessor(BaseProcessor):
    """Normalizes sensor values to standard range.

    Uses configured normalization strategies (identity, minmax, etc.)
    to scale sensor readings to a consistent range (typically [0, 1]).

    Parameters
    ----------
    config_manager : ConfigurationManager
        Configuration manager providing normalization strategies.
    """

    def __init__(self, config_manager) -> None:
        """Initialize the normalization processor.

        Parameters
        ----------
        config_manager : ConfigurationManager
            Configuration manager for strategy resolution.
        """
        self._config_manager: ConfigurationManager = config_manager

    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Apply normalization to the smoothed value.

        Parameters
        ----------
        context : ProcessingContext
            Current processing context with smoothed_value set.

        Returns
        -------
        ProcessingContext
            Updated context with normalized_value and normalization_profile_id set.
        """
        reading = context.calibrated_reading
        if reading is None:
            raise ValueError("NormalizationProcessor requires calibrated_reading to be set")

        sensor_key = context.sensor_key
        sensor_id = reading.sensor_id

        # Get normalization strategy
        if sensor_key is None:
            raise ValueError("NormalizationProcessor requires sensor_key to be set in context")
        strategy, profile = self._config_manager.get_normalization_strategy(sensor_key, sensor_id)

        # Apply normalization to smoothed value
        value = context.get_final_value()
        normalized = float(strategy.apply(value))

        context.normalized_value = normalized
        context.normalization_profile_id = profile.profile_id

        logger.debug(
            f"Normalized sensor_id={sensor_id}: {value} -> {normalized} "
            f"(profile={profile.profile_id})"
        )

        return context
