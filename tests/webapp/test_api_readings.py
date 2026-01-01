
import pytest
from flask import Flask
from unittest.mock import MagicMock
from dt.communication.db_client import DatabaseApiClient
from dt.communication.dataclasses.queries import ReadingsQuery
from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.aggregated_reading import AggregatedReading
from dt.webapp.api import create_webapp_blueprint

@pytest.fixture
def db_client_mock():
    return MagicMock(spec=DatabaseApiClient)

@pytest.fixture
def app(db_client_mock):
    app = Flask(__name__)
    bp = create_webapp_blueprint(db_client_mock)
    app.register_blueprint(bp)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_get_readings_timestamp_conversion(client, db_client_mock):
    """Test that timestamps are converted from ms to seconds for the DB query."""
    # Setup mock return value
    db_client_mock.query_readings.return_value = []

    # Client requests with ms timestamps
    since_ms = 1700000000000
    until_ms = 1700000060000
    
    response = client.get(f"/api/readings?since={since_ms}&until={until_ms}&topic=temp")
    
    assert response.status_code == 200
    
    # Check if DB client was called with seconds
    db_client_mock.query_readings.assert_called_once()
    call_args = db_client_mock.query_readings.call_args[0][0]
    assert isinstance(call_args, ReadingsQuery)
    assert call_args.since == since_ms / 1000.0
    assert call_args.until == until_ms / 1000.0
    assert call_args.topic == "temp"

def test_get_readings_response_shape(client, db_client_mock):
    """Test that the response converts internal timestamps (seconds) back to ms."""
    # Setup mock return
    processed_data = ProcessedSensorData(
        plant_id=1,
        sensor_id=1,
        timestamp=1700000000.0, # seconds
        value=25.0,
        unit="C",
        topic="dt.sensors.temperature",
        correlation_id="abc",
        raw_value=24.5,
        calibrated_value=25.0,
        normalized_value=0.5,
        dq_score=1.0,
        imputed=False,
        flags={"valid_data_point": True}
    )
    db_client_mock.query_readings.return_value = [processed_data]

    response = client.get("/api/readings?topic=temp")
    data = response.get_json()

    assert len(data) == 1
    item = data[0]
    # Verify timestamp conversion s -> ms and renaming
    assert item["time"] == 1700000000000
    assert "timestamp" not in item
    # Verify snake_case keys from ProcessedSensorData
    assert item["value"] == 25.0
    assert item["raw_value"] == 24.5


def test_get_readings_aggregate_bucket_conversion(client, db_client_mock):
    """Test that aggregate bucket timestamps are converted to ms and renamed to time."""
    aggregate = AggregatedReading(
        bucket=1700000000.0,
        sensor_id=1,
        plant_id=1,
        topic="dt.sensors.temperature",
        unit="C",
        avg_value=25.0,
        min_value=24.0,
        max_value=26.0,
        sample_count=12,
        avg_dq_score=0.9,
        imputed_count=0,
    )
    db_client_mock.query_readings.return_value = [aggregate]

    response = client.get("/api/readings?window=1h&topic=dt.sensors.temperature")
    assert response.status_code == 200

    data = response.get_json()
    assert len(data) == 1
    assert data[0]["time"] == 1700000000000
    assert "bucket" not in data[0]
