from enum import StrEnum


class Config(StrEnum):

    KAFKA_URL = "91.86.62.242:9092"  # Kafka messaging service URL

    # Database configuration
    INFLUX_URL = "http://localhost:8086"  # InfluxDB URL
    INFLUX_TOKEN = (
        "ttX_TQAsmsu9SAJ0xUGosEdA72b6DJoIFhbOYK8iRzRMHl5dggZAJwbPsGjxt8K-mgdSIPKEkuXUIsGOWxDotA=="
    )
    INFLUX_ORG = "dt-ulb"  # InfluxDB organization
    INFLUX_BUCKET = "plant-health-monitoring"  # InfluxDB bucket

    # Flask server URLs
    FLASK_DB_URL = "http://localhost:5001/"
    FLASK_DASHBOARD_URL = "http://localhost:5000/"
