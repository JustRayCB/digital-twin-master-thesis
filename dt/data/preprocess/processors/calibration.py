from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.configuration.manager import ConfigurationManager
from dt.data.preprocess.pipeline.context import ProcessingContext
from dt.data.preprocess.processors.base import BaseProcessor
from dt.utils import get_logger

logger = get_logger(__name__)


class CalibrationProcessor(BaseProcessor):
    """Applies calibration transformation to raw sensor readings.

    Parameters
    ----------
    config_manager : ConfigurationManager
        Configuration manager providing calibration strategies.
    """

    def __init__(self, config_manager: ConfigurationManager) -> None:
        """Initialize the calibration processor.

        Parameters
        ----------
        config_manager : ConfigurationManager
            Configuration manager for strategy resolution.
        """
        self._config_manager: ConfigurationManager = config_manager

    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Apply calibration to the raw reading.

        Parameters
        ----------
        context : ProcessingContext
            Current processing context.

        Returns
        -------
        ProcessingContext
            Updated context with calibrated_reading and calibration_profile_id set.
        """
        reading = context.reading
        sensor_key = context.sensor_key
        sensor_id = reading.sensor_id
        if sensor_key is None or sensor_id is None:
            raise ValueError("Sensor key and sensor ID must be set in the Pipeline context.")

        # Get calibration strategy
        strategy, profile = self._config_manager.get_calibration_strategy(sensor_key, sensor_id)

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
        context.calibration_profile_id = profile.profile_id

        logger.debug(
            f"Calibrated sensor_id={sensor_id}: {reading.value} -> {calibrated_value} "
            f"(profile={profile.profile_id})"
        )

        return context
