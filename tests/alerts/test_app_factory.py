"""Tests for alert engine application factory."""

from unittest.mock import Mock, patch

import pytest
from flask import Flask


@pytest.fixture
def mock_kafka_service():
    """Create a mock KafkaService that successfully connects."""
    with patch("dt.alerts.app.KafkaService") as mock_class:
        mock_instance = Mock()
        mock_instance.connect = Mock(return_value=True)
        mock_instance.disconnect = Mock()
        mock_class.return_value = mock_instance
        yield mock_instance


def test_create_app_returns_flask_instance(mock_kafka_service):
    """Test that create_app returns a Flask application instance."""
    from dt.alerts.app import create_app

    app = create_app(start_consumer=False)

    assert isinstance(app, Flask)
    assert app is not None


def test_create_app_registers_alert_blueprint(mock_kafka_service):
    """Test that alert blueprint is registered with the app."""
    from dt.alerts.app import create_app

    app = create_app(start_consumer=False)

    # Check that the alerts blueprint is registered
    assert "alerts" in app.blueprints
    assert app.blueprints["alerts"].url_prefix == "/alerts"


def test_create_app_registers_rules_blueprint(mock_kafka_service):
    """Test that alert-rules blueprint is registered with the app."""
    from dt.alerts.app import create_app

    app = create_app(start_consumer=False)

    # Check that the alert_rules blueprint is registered
    assert "alert_rules" in app.blueprints


def test_create_app_does_not_start_consumer_when_disabled(mock_kafka_service):
    """Test that consumer is not started when start_consumer=False."""
    from dt.alerts.app import create_app

    with patch("dt.alerts.app.AlertEngineService") as mock_service_class:
        mock_service_instance = Mock()
        mock_service_class.return_value = mock_service_instance

        app = create_app(start_consumer=False)

        # Verify service start was NOT called
        mock_service_instance.start.assert_not_called()


def test_create_app_starts_consumer_when_enabled(mock_kafka_service):
    """Test that consumer is started when start_consumer=True."""
    from dt.alerts.app import create_app

    with patch("dt.alerts.app.AlertEngineService") as mock_service_class:
        mock_service_instance = Mock()
        mock_service_class.return_value = mock_service_instance

        app = create_app(start_consumer=True)

        # Verify service start was called
        mock_service_instance.start.assert_called_once()


def test_create_app_loads_alert_rules(mock_kafka_service):
    """Test that alert rules are loaded from config."""
    from dt.alerts.app import create_app

    with patch("dt.alerts.app.build_alert_rule_manager") as mock_build:
        mock_manager = Mock()
        mock_manager.rules = []
        mock_manager.__len__ = Mock(return_value=0)
        mock_build.return_value = mock_manager

        app = create_app(start_consumer=False)

        # Verify rule manager was built
        mock_build.assert_called_once()


def test_create_app_alert_endpoints_exist(mock_kafka_service):
    """Test that alert API endpoints are accessible."""
    from dt.alerts.app import create_app

    app = create_app(start_consumer=False)
    client = app.test_client()

    # Test /alerts/active endpoint exists (should return 200 with empty list)
    response = client.get("/alerts/active")
    assert response.status_code == 200

    # Test /alert-rules endpoint exists
    response = client.get("/alert-rules")
    assert response.status_code == 200


def test_create_app_submit_endpoint_accepts_post(mock_kafka_service):
    """Test that /alerts/submit accepts POST requests."""
    from dt.alerts.app import create_app

    app = create_app(start_consumer=False)
    client = app.test_client()

    # Test that submit endpoint exists and accepts POST
    # (should fail validation but endpoint should exist)
    response = client.post("/alerts/submit", json={})
    # Should return 400 (bad request) not 404 (not found)
    assert response.status_code in [400, 500]


def test_create_app_with_custom_config_path(mock_kafka_service):
    """Test that create_app accepts custom config path."""
    from dt.alerts.app import create_app

    with patch("dt.alerts.app.build_alert_rule_manager") as mock_build:
        mock_manager = Mock()
        mock_manager.rules = []
        mock_manager.__len__ = Mock(return_value=0)
        mock_build.return_value = mock_manager

        custom_path = "/custom/path/to/rules.yml"
        app = create_app(start_consumer=False, config_path=custom_path)

        # Verify custom path was used
        mock_build.assert_called_once_with(custom_path)


def test_run_helper_exists():
    """Test that run() helper function exists."""
    from dt.alerts.app import run

    # Verify the run function is callable
    assert callable(run)


def test_app_stores_service_components(mock_kafka_service):
    """Test that app stores references to service components."""
    from dt.alerts.app import create_app

    app = create_app(start_consumer=False)

    # Verify app config contains necessary service components
    assert hasattr(app, "config")
    assert "ALERT_REGISTRY" in app.config
    assert "ALERT_PUBLISHER" in app.config
    assert "ALERT_RULE_MANAGER" in app.config
