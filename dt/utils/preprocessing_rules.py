from dt.communication.dataclasses.preprocessing_config import SensorValidationConfig
from dt.utils.config import Config

# Load configuration from default path
PREPROCESSING_CONFIG = SensorValidationConfig.load(Config.PREPROCESSING_CONFIG_PATH)
