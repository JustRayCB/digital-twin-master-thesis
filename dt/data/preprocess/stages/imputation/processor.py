from dt.data.preprocess.core.context import ProcessingContext
from dt.data.preprocess.stages.base import BaseProcessor
from dt.utils import get_logger
from dt.utils.exceptions.drop_reading import DropReadingException

logger = get_logger(__name__)


class ImputationProcessor(BaseProcessor):
    """Imputes invalid sensor readings using configured strategies.

    For invalid readings, attempts to estimate a plausible value based on
    historical context using the configured imputation strategy. If imputation
    fails (e.g., no historical data available), raises DropReadingException.

    Parameters
    ----------
    config_manager : ConfigurationManager
        Configuration manager providing imputation strategies.
    """

    def __init__(self, config_manager) -> None:
        """Initialize the imputation processor.

        Parameters
        ----------
        config_manager : ConfigurationManager
            Configuration manager for strategy resolution.
        """
        self._config_manager = config_manager

    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Impute invalid readings or pass through valid ones.

        Parameters
        ----------
        context : ProcessingContext
            Current processing context with is_valid set.

        Returns
        -------
        ProcessingContext
            Updated context with imputed=True and imputed_value set if imputed.

        Raises
        ------
        DropReadingException
            When imputation fails and the reading cannot be recovered.
        ValueError
            If required fields in context are missing.
        """
        reading = context.calibrated_reading
        if reading is None:
            raise ValueError("ImputationProcessor requires calibrated_reading to be set")
        # Skip imputation for valid readings
        if context.is_valid:
            context.imputed = False
            context.imputed_value = None
            return context

        sensor_config = context.sensor_config
        sensor_key = context.sensor_key
        sensor_id = reading.sensor_id
        state_provider = context.state_provider

        # Get imputation strategy
        if sensor_key is None or sensor_config is None:
            raise ValueError("ImputationProcessor requires sensor_key and sensor_config to be set")
        strategy = self._config_manager.get_imputation_strategy(sensor_key, reading.topic)

        # Attempt imputation
        try:
            imputed_value = strategy.compute(
                sensor_id=sensor_id,
                reading=reading,
                state=state_provider,
            )
        except Exception as exc:
            logger.warning(
                f"Imputation strategy raised for sensor_id={sensor_id} at timestamp={reading.timestamp}: {exc}",
            )
            raise DropReadingException(
                f"Cannot impute reading for sensor_id={sensor_id}",
                context=context,
            ) from exc

        if imputed_value is None:
            # Imputation failed - drop the reading
            logger.warning(
                f"Imputation failed for sensor_id={sensor_id} at timestamp={reading.timestamp}"
            )
            raise DropReadingException(
                f"Cannot impute reading for sensor_id={sensor_id}",
                context=context,
            )

        context.imputed = True
        context.imputed_value = float(imputed_value)

        logger.debug(
            f"Imputed sensor_id={sensor_id}: {reading.value} -> {imputed_value} "
            f"(strategy={strategy.__class__.__name__})"
        )
        return context
