from dt.data.preprocess.config.manager import ConfigurationManager
from dt.utils.config import Config

# Load configuration using the new manager
PREPROCESSING_CONFIG = ConfigurationManager(Config.PREPROCESSING_CONFIG_PATH)