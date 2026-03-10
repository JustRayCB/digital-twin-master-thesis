from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.core.context import ProcessingContext
from dt.data.preprocess.stages.base import BaseProcessor
from dt.utils import get_logger

logger = get_logger(__name__)


class CalibrationProcessor(BaseProcessor):
    """Applies calibration transformation to raw sensor readings.

    Parameters
    ----------
    config_manager : ConfigurationManager
        Configuration manager providing calibration strategies.
    """

    def __init__(self, config_manager) -> None:
        """Initialize the calibration processor.

        Parameters
        ----------
        config_manager : ConfigurationManager
            Configuration manager for strategy resolution.
        """
        self._config_manager = config_manager

    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Apply calibration to the raw reading.

        Parameters
        ----------
        context : ProcessingContext
            Updated context with calibrated_reading set.
        """
        if context.sensor_key is None:
            raise ValueError("CalibrationProcessor requires sensor_key to be set")
        if context.sensor_config is None:
            raise ValueError("CalibrationProcessor requires sensor_config to be set")

        reading = context.reading
        sensor_name = context.sensor_key

        # Get calibration strategy
        strategy = self._config_manager.get_calibration_strategy(sensor_name, reading.topic)

        # Apply calibration
        calibrated_value = strategy.apply(float(reading.value))

        # Create calibrated reading
        context.calibrated_reading = RawSensorData(
            plant_id=reading.plant_id,
            sensor_id=reading.sensor_id,
            timestamp=reading.timestamp,
            value=calibrated_value,
            unit=reading.unit,
            topic=reading.topic,
            correlation_id=reading.correlation_id,
        )

        context.calibration_profile_id = context.sensor_config.calibration_profile_id or ""

        logger.debug(f"Calibrated {sensor_name}: {reading.value} -> {calibrated_value}")

        return context
