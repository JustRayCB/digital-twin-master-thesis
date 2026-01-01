import re

from dt.communication.topics import Topics
from dt.webapp.demo import build_demo_alert_payload, build_demo_processed_payload


def test_build_demo_processed_payload_has_required_keys_and_ms_timestamp():
    payload = build_demo_processed_payload(
        plant_id=1,
        sensor_id=2,
        unit="C",
        time_ms=1735689600000,
        value=22.5,
        raw_value=22.0,
        calibrated_value=22.6,
        normalized_value=0.4,
        dq_score=0.95,
        flags={"valid_data_point": True, "range_violation": False},
        correlation_id="corr-123",
        calibration_profile_id="cal-v1",
        normalization_profile_id="norm-v2",
    )

    assert payload["plant_id"] == 1
    assert payload["sensor_id"] == 2
    assert payload["unit"] == "C"
    assert payload["time"] == 1735689600000
    assert payload["value"] == 22.5
    assert payload["raw_value"] == 22.0
    assert payload["calibrated_value"] == 22.6
    assert payload["normalized_value"] == 0.4
    assert payload["dq_score"] == 0.95
    assert payload["flags"]["valid_data_point"] is True
    assert payload["correlation_id"] == "corr-123"
    assert payload["calibration_profile_id"] == "cal-v1"
    assert payload["normalization_profile_id"] == "norm-v2"


def test_demo_processed_value_can_differ_from_raw_and_calibrated():
    payload = build_demo_processed_payload(
        plant_id=1,
        sensor_id=2,
        unit="C",
        time_ms=1735689600000,
        value=22.5,
        raw_value=22.0,
        calibrated_value=22.6,
        normalized_value=0.4,
        dq_score=0.95,
        flags={"valid_data_point": True, "range_violation": False},
        correlation_id="corr-123",
        calibration_profile_id="cal-v1",
        normalization_profile_id="norm-v2",
    )

    assert payload["value"] != payload["raw_value"]
    assert payload["value"] != payload["calibrated_value"]


def test_build_demo_alert_payload_has_alert_id_and_ms_timestamp():
    payload = build_demo_alert_payload(
        plant_id=1,
        alert_key="soil_moisture_low",
        time_ms=1735689600000,
        status="active",
        severity="warning",
        message="Soil moisture below threshold",
        correlation_id="corr-123",
        acknowledged_by=None,
        acknowledged_ts=None,
        cleared_ts=None,
    )

    assert payload["plant_id"] == 1
    assert payload["alert_key"] == "soil_moisture_low"
    assert payload["alert_id"] == "1:soil_moisture_low"
    assert payload["time"] == 1735689600000
    assert payload["severity"] == "warning"
    assert payload["status"] == "active"
    assert payload["correlation_id"] == "corr-123"


def test_demo_topic_name_matches_frontend_expectation():
    assert Topics.TEMPERATURE.processed == "dt.sensors.processed.temperature"
    assert re.match(r"^dt\.sensors\.processed\.[a-z_]+$", Topics.SOIL_MOISTURE.processed)
