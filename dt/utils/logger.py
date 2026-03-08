import logging
import os
import sys
from datetime import datetime

# Create logs directory if it doesn't exist
LOG_DIR = os.path.join(os.path.abspath(os.path.join(__file__, "../../..")), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Get current date for log file naming
current_date = datetime.now().strftime("%Y-%m-%d")
LOG_FILE = os.path.join(LOG_DIR, f"plant_twin_{current_date}.log")


# Configure logging
def get_logger(name: str):
    """Create and configure a logger.

    This function sets up a logger that writes to both the console (INFO level
    and above) and a rotating daily log file (DEBUG level and above). It ensures
    that handlers are not duplicated if the logger has already been configured.

    Parameters
    ----------
    name : str
        The name of the logger, typically the ``__name__`` of the calling module.

    Returns
    -------
    logging.Logger
        A configured logger instance.

    Examples
    --------
    >>> logger = get_logger(__name__)
    >>> logger.info("This is an informational message.")
    >>> logger.debug("This is a debug message.")
    """

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers
    if logger.hasHandlers():
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)

    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
