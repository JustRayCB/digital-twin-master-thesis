import os
from enum import StrEnum

from dotenv import load_dotenv

load_dotenv()


class Config(StrEnum):

    KAFKA_URL = os.getenv("KAFKA_URL", "localhost:9092")  # Kafka broker URL

    # Database configuration
    INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")  # InfluxDB URL
    INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN", "my-influxdb-token")  # InfluxDB token
    INFLUX_ORG = os.getenv("INFLUXDB_ORG", "dt-ulb")  # InfluxDB organization
    INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET", "dt-ulb-bucket")  # InfluxDB bucket

    # Flask server URLs
    FLASK_DASHBOARD_URL = os.getenv(
        "FLASK_DASHBOARD_URL", "http://localhost:5000/"
    )  # Dashboard URL
    FLASK_DB_URL = os.getenv("FLASK_DB_URL", "http://localhost:5001/")  # Database service URL
    FLASK_AI_URL = os.getenv("FLASK_AI_URL", "http://localhost:5002/")  # AI service URL

    MODELS_DIR = os.getenv("MODELS_DIR", "models/")  # Directory to save/load models
