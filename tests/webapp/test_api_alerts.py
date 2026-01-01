
import pytest
from flask import Flask
from unittest.mock import MagicMock
from dt.communication.db_client import DatabaseApiClient
from dt.communication.dataclasses.queries import AlertHistoryQuery
from dt.communication.dataclasses.alerts.alert_record import AlertHistoryEvent
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

def test_get_active_alerts(client, db_client_mock):
    """Test fetching active alerts and timestamp conversion."""
    alert = AlertHistoryEvent(
        alert_key="temp_high",
        plant_id=1,
        timestamp=1700000000.0,
        status="active",
        severity="warning",
        message="Too hot",
        correlation_id="abc"
    )
    db_client_mock.get_active_alerts.return_value = [alert]

    response = client.get("/api/alerts/active?plant_id=1")
    
    assert response.status_code == 200
    db_client_mock.get_active_alerts.assert_called_once()
    
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["time"] == 1700000000000
    assert "timestamp" not in data[0]
    assert data[0]["alert_key"] == "temp_high"

def test_get_alert_history_params(client, db_client_mock):
    """Test alert history query params conversion."""
    db_client_mock.get_alert_history.return_value = []
    
    # AlertHistoryQuery only supports plant_id and limit
    client.get("/api/alerts/history?plant_id=1&limit=50")
    
    db_client_mock.get_alert_history.assert_called_once()
    call_args = db_client_mock.get_alert_history.call_args[0][0]
    
    assert isinstance(call_args, AlertHistoryQuery)
    assert call_args.plant_id == 1
    assert call_args.limit == 50
