"""Tests for alert payload shaping and active-alert cache updates."""

from dt.alerts.rules import SeverityLevel
from dt.communication.dataclasses.alerts.alert_record import AlertHistoryEvent, AlertStatus
from dt.webapp.consumer import apply_alert_event_to_cache, shape_alert_event_payload


def test_shape_alert_event_payload_emits_ms_timestamp_and_expected_keys():
    """Ensure alert payload matches the browser contract (ms timestamps, stable keys)."""
    event = AlertHistoryEvent(
        alert_key="soil_moisture_low",
        plant_id=1,
        timestamp=1735689600.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Soil moisture below threshold",
        correlation_id="corr-123",
    )

    payload = shape_alert_event_payload(event)

    assert payload == {
        "alert_id": "1:soil_moisture_low",
        "alert_key": "soil_moisture_low",
        "plant_id": 1,
        "time": 1735689600000,
        "status": "active",
        "severity": "warning",
        "message": "Soil moisture below threshold",
        "correlation_id": "corr-123",
        "acknowledged_by": None,
        "acknowledged_ts": None,
        "cleared_ts": None,
    }


def test_apply_alert_event_to_cache_updates_and_clears_cache():
    """Ensure active cache updates for ACTIVE/ACKNOWLEDGED and removes for CLEARED."""
    cache: dict[str, dict] = {}

    active_event = AlertHistoryEvent(
        alert_key="soil_moisture_low",
        plant_id=1,
        timestamp=10.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="msg",
        correlation_id="corr",
    )
    emitted = apply_alert_event_to_cache(cache, active_event)
    assert list(cache.keys()) == ["1:soil_moisture_low"]
    assert [name for name, _payload in emitted] == ["alerts_update"]

    acknowledged_event = AlertHistoryEvent(
        alert_key="soil_moisture_low",
        plant_id=1,
        timestamp=11.0,
        status=AlertStatus.ACKNOWLEDGED,
        severity=SeverityLevel.WARNING,
        message="msg",
        correlation_id="corr",
        acknowledged_by="ray",
        acknowledged_ts=11.0,
    )
    emitted = apply_alert_event_to_cache(cache, acknowledged_event)
    assert list(cache.keys()) == ["1:soil_moisture_low"]
    assert cache["1:soil_moisture_low"]["status"] == "acknowledged"
    assert [name for name, _payload in emitted] == ["alerts_update"]

    cleared_event = AlertHistoryEvent(
        alert_key="soil_moisture_low",
        plant_id=1,
        timestamp=12.0,
        status=AlertStatus.CLEARED,
        severity=SeverityLevel.WARNING,
        message="msg",
        correlation_id="corr",
    )
    emitted = apply_alert_event_to_cache(cache, cleared_event)
    assert cache == {}
    assert [name for name, _payload in emitted] == ["alerts_remove"]
