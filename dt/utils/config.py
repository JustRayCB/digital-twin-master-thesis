import os
from enum import StrEnum

from dotenv import load_dotenv

load_dotenv()


class Config(StrEnum):

    KAFKA_URL = os.getenv("KAFKA_URL", "localhost:9092")  # Kafka broker URL

    # PostgreSQL + TimescaleDB configuration
    PG_DATABASE_URL = os.getenv(
        "PG_DATABASE_URL", "postgresql+psycopg://dt:dt@localhost:5432/dt"
    )  # PostgreSQL connection URL
    SQL_POOL_SIZE = os.getenv("SQL_POOL_SIZE", "5")  # SQLAlchemy connection pool size
    DB_MIGRATIONS_DIR = os.getenv(
        "DB_MIGRATIONS_DIR", "dt/data/database/migrations"
    )  # Migrations directory
    SNAPSHOT_STORAGE_ROOT = os.getenv(
        "SNAPSHOT_STORAGE_ROOT", "data/camera_snapshots"
    )  # Filesystem root for persisted camera snapshots

    # Flask server URLs
    FLASK_DASHBOARD_URL = os.getenv(
        "FLASK_DASHBOARD_URL", "http://localhost:5000/"
    )  # Dashboard URL
    FLASK_DB_URL = os.getenv("FLASK_DB_URL", "http://localhost:5001/")  # Database service URL
    FLASK_AI_URL = os.getenv("FLASK_AI_URL", "http://localhost:5002/")  # AI service URL
    DEBUG_MODE = os.getenv("FLASK_DEBUG", "True")  # Flask debug toggle

    MODELS_DIR = os.getenv("MODELS_DIR", "models/")  # Directory to save/load models

    # SPARK CONFIGURATION
    PREPROCESSING_CONFIG_PATH = os.getenv(
        "PREPROCESSING_CONFIG_PATH", "dt/utils/preprocessing_config.yml"
    )  # Path to preprocessing config file

    PREPROCESSING_CHECKPOINT_DIR = os.getenv(
        "PREPROCESSING_CHECKPOINT_DIR", "./spark-checkpoints/preprocessing"
    )  # Default checkpoint directory for the preprocessing job

    MAX_STATE_HISTORY_LENGTH = os.getenv(
        "MAX_STATE_HISTORY_LENGTH", "64"
    )  # Max length of state history
    SPARK_LOG_LEVEL = os.getenv("SPARK_LOG_LEVEL", "WARN")  # Spark log level
    SPARK_APP_NAME = os.getenv("SPARK_APP_NAME", "dt-preprocessing-app")  # Spark application name
    SPARK_MASTER = os.getenv("SPARK_MASTER", "local[2]")  # Spark master URL
    SPARK_LOCAL_IP = os.getenv(
        "SPARK_LOCAL_IP", "127.0.0.1"
    )  # Driver address for the single-host deployment
    SPARK_SQL_SHUFFLE_PARTITIONS = os.getenv(
        "SPARK_SQL_SHUFFLE_PARTITIONS", "2"
    )  # Shuffle partitions
    SPARK_DEFAULT_PARALLELISM = os.getenv("SPARK_DEFAULT_PARALLELISM", "2")  # Default parallelism
    SPARK_AQE_ENABLED = os.getenv("SPARK_AQE_ENABLED", "false")  # Adaptive query execution
    SPARK_MAX_OFFSETS_PER_TRIGGER = os.getenv(
        "SPARK_MAX_OFFSETS_PER_TRIGGER", "500"
    )  # Kafka offsets per trigger
    SPARK_TRIGGER_INTERVAL = os.getenv(
        "SPARK_TRIGGER_INTERVAL", "5 seconds"
    )  # Processing time trigger
    SPARK_WATERMARK_INTERVAL = os.getenv(
        "SPARK_WATERMARK_INTERVAL", "10 minutes"
    )  # Watermark delay
    SPARK_STATE_TIMEOUT_SECONDS = os.getenv(
        "SPARK_STATE_TIMEOUT_SECONDS", "600"
    )  # Group state timeout (seconds)
    SPARK_STARTING_OFFSETS = os.getenv(
        "STARTING_OFFSETS", "latest"
    )  # Kafka starting offsets for streaming

    # ALERT ENGINE CONFIGURATION
    ALERT_RULES_PATH = os.getenv(
        "ALERT_RULES_PATH", "dt/utils/alert_rules.yml"
    )  # Path to alert rules configuration file

    # CONTROLLER CONFIGURATION
    FLASK_CONTROLLER_URL = os.getenv(
        "FLASK_CONTROLLER_URL", "http://localhost:5004/"
    )  # Controller service URL
    ESP32_CAMERA_SNAPSHOT_URL = os.getenv(
        "ESP32_CAMERA_SNAPSHOT_URL", "http://192.168.50.10/snapshot"
    )  # ESP32 camera snapshot endpoint
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Brussels")  # Timezone for scheduling
