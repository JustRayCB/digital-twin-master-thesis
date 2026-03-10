"""Tests for alert rule configuration loader."""

import pytest
import yaml

from dt.alerts.rules import AlertRule, ConditionType, EvaluationStage, SeverityLevel
from dt.alerts.rule_manager import build_alert_rule_manager


@pytest.fixture
def sample_rules_yaml(tmp_path):
    """Create a sample alert rules YAML file.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory for test files.

    Returns
    -------
    pathlib.Path
        Path to the alert rules YAML file.
    """
    config = {
        "alert_rules": [
            {
                "rule_id": "temp_high",
                "name": "High Temperature Alert",
                "description": "Temperature exceeds {threshold}°C",
                "severity": "warning",
                "evaluation_stage": "processed",
                "source": "temperature",
                "condition": {
                    "type": "threshold",
                    "operator": ">",
                    "threshold": 35.0,
                },
                "persistence_count": 2,
                "cooldown_seconds": 300,
            },
            {
                "rule_id": "moisture_low",
                "name": "Low Moisture Alert",
                "description": "Soil moisture below {min_value}%",
                "severity": "critical",
                "evaluation_stage": "processed",
                "source": "soil_moisture",
                "condition": {
                    "type": "range",
                    "min_value": 20.0,
                    "max_value": None,
                },
                "persistence_count": 3,
                "cooldown_seconds": 600,
            },
            {
                "rule_id": "dq_low",
                "name": "Low Data Quality",
                "description": "Data quality score below {threshold}",
                "severity": "info",
                "evaluation_stage": "processed",
                "source": "*",
                "condition": {
                    "type": "dq_score",
                    "threshold": 0.7,
                },
                "persistence_count": 1,
                "cooldown_seconds": 120,
            },
        ]
    }
    config_file = tmp_path / "alert_rules.yml"
    config_file.write_text(yaml.dump(config))
    return config_file


def test_load_well_formed_config(sample_rules_yaml):
    """Test successful loading of a well-formed configuration.

    Parameters
    ----------
    sample_rules_yaml : pathlib.Path
        Path to the alert rules YAML file.

    Returns
    -------
    None
        The assertions raise if rule loading regresses.
    """
    rules = build_alert_rule_manager(str(sample_rules_yaml)).rules

    assert len(rules) == 3
    assert all(isinstance(rule, AlertRule) for rule in rules)

    # Verify first rule
    temp_rule = rules[0]
    assert temp_rule.rule_id == "temp_high"
    assert temp_rule.name == "High Temperature Alert"
    assert temp_rule.severity == SeverityLevel.WARNING
    assert temp_rule.evaluation_stage == EvaluationStage.PROCESSED
    assert temp_rule.source == "temperature"
    assert temp_rule.condition.type == ConditionType.THRESHOLD
    assert temp_rule.persistence_count == 2
    assert temp_rule.cooldown_seconds == 300


def test_invalid_severity_raises_error(tmp_path):
    """Test that invalid severity level raises descriptive error.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory for test files.

    Returns
    -------
    None
        The assertions raise if validation regresses.
    """
    config = {
        "alert_rules": [
            {
                "rule_id": "test_rule",
                "name": "Test Rule",
                "description": "Test",
                "severity": "super_critical",  # Invalid
                "evaluation_stage": "processed",
                "source": "temperature",
                "condition": {"type": "threshold", "operator": ">", "threshold": 30.0},
                "persistence_count": 1,
                "cooldown_seconds": 60,
            }
        ]
    }
    config_file = tmp_path / "invalid_severity.yml"
    config_file.write_text(yaml.dump(config))

    with pytest.raises(ValueError, match="Invalid severity"):
        build_alert_rule_manager(str(config_file))


def test_invalid_condition_type_raises_error(tmp_path):
    """Test that invalid condition type raises descriptive error.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory for test files.

    Returns
    -------
    None
        The assertions raise if validation regresses.
    """
    config = {
        "alert_rules": [
            {
                "rule_id": "test_rule",
                "name": "Test Rule",
                "description": "Test",
                "severity": "warning",
                "evaluation_stage": "processed",
                "source": "temperature",
                "condition": {"type": "magic_detection"},  # Invalid
                "persistence_count": 1,
                "cooldown_seconds": 60,
            }
        ]
    }
    config_file = tmp_path / "invalid_condition.yml"
    config_file.write_text(yaml.dump(config))

    with pytest.raises(ValueError, match="Invalid condition type"):
        build_alert_rule_manager(str(config_file))


def test_invalid_evaluation_stage_raises_error(tmp_path):
    """Test that invalid evaluation stage raises descriptive error.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory for test files.

    Returns
    -------
    None
        The assertions raise if validation regresses.
    """
    config = {
        "alert_rules": [
            {
                "rule_id": "test_rule",
                "name": "Test Rule",
                "description": "Test",
                "severity": "warning",
                "evaluation_stage": "ultra_processed",  # Invalid
                "source": "temperature",
                "condition": {"type": "threshold", "operator": ">", "threshold": 30.0},
                "persistence_count": 1,
                "cooldown_seconds": 60,
            }
        ]
    }
    config_file = tmp_path / "invalid_stage.yml"
    config_file.write_text(yaml.dump(config))

    with pytest.raises(ValueError, match="Invalid evaluation stage"):
        build_alert_rule_manager(str(config_file))


def test_missing_required_fields_raises_error(tmp_path):
    """Test that missing required fields produces error.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory for test files.

    Returns
    -------
    None
        The assertions raise if validation regresses.
    """
    config = {
        "alert_rules": [
            {
                "rule_id": "test_rule",
                # Missing name, description, severity, etc.
                "condition": {"type": "threshold", "operator": ">", "threshold": 30.0},
            }
        ]
    }
    config_file = tmp_path / "missing_fields.yml"
    config_file.write_text(yaml.dump(config))

    with pytest.raises((ValueError, KeyError)):
        build_alert_rule_manager(str(config_file))


def test_override_hook_merges_correctly(sample_rules_yaml):
    """Test that override hook merges dynamic overrides with loaded rules.

    Parameters
    ----------
    sample_rules_yaml : pathlib.Path
        Path to the alert rules YAML file.

    Returns
    -------
    None
        The assertions raise if override merging regresses.
    """
    # Create manager and load base rules
    manager = build_alert_rule_manager(str(sample_rules_yaml))

    # Define dynamic overrides
    overrides = {
        "temp_high": {
            "condition": {"type": "threshold", "operator": ">", "threshold": 40.0},
            "cooldown_seconds": 450,
        },
        "new_rule": {
            "rule_id": "new_rule",
            "name": "New Dynamic Rule",
            "description": "Dynamically added",
            "severity": "warning",
            "evaluation_stage": "processed",
            "source": "humidity",
            "condition": {"type": "threshold", "operator": "<", "threshold": 30.0},
            "persistence_count": 1,
            "cooldown_seconds": 60,
        },
    }

    # Merge overrides using the same manager instance
    merged_rules = manager.merge_overrides(overrides)

    # Verify override was applied to existing rule
    temp_rule = next(r for r in merged_rules if r.rule_id == "temp_high")
    assert temp_rule.condition.threshold == 40.0  # Updated
    assert temp_rule.cooldown_seconds == 450  # Updated
    assert temp_rule.name == "High Temperature Alert"  # Preserved

    # Verify new rule was added
    new_rule = next(r for r in merged_rules if r.rule_id == "new_rule")
    assert new_rule.name == "New Dynamic Rule"
    assert new_rule.source == "humidity"

    # Verify unchanged rules are preserved
    assert any(r.rule_id == "moisture_low" for r in merged_rules)


def test_empty_config_returns_empty_list(tmp_path):
    """Test that empty configuration returns empty list."""
    config = {"alert_rules": []}
    config_file = tmp_path / "empty.yml"
    config_file.write_text(yaml.dump(config))

    rules = build_alert_rule_manager(str(config_file)).rules
    assert rules == []


def test_malformed_yaml_raises_error(tmp_path):
    """Test that malformed YAML (empty file) raises descriptive error."""
    config_file = tmp_path / "malformed.yml"
    config_file.write_text("")  # Empty file returns None from yaml.safe_load

    with pytest.raises(ValueError, match="Invalid alert rules configuration"):
        build_alert_rule_manager(str(config_file))


def test_non_dict_yaml_raises_error(tmp_path):
    """Test that non-dictionary YAML raises descriptive error."""
    config_file = tmp_path / "non_dict.yml"
    config_file.write_text("- item1\n- item2")  # List instead of dict

    with pytest.raises(ValueError, match="Invalid alert rules configuration"):
        build_alert_rule_manager(str(config_file))


def test_load_rule_with_active_hours(sample_rules_yaml, tmp_path):
    """Rules can define an optional local-time active window."""
    config = yaml.safe_load(sample_rules_yaml.read_text())
    config["alert_rules"][0]["active_hours"] = {"start": "08:00", "end": "20:00"}

    config_file = tmp_path / "active_hours.yml"
    config_file.write_text(yaml.dump(config))

    rules = build_alert_rule_manager(str(config_file)).rules

    assert rules[0].active_hours is not None
    assert rules[0].active_hours.start.hour == 8
    assert rules[0].active_hours.start.minute == 0
    assert rules[0].active_hours.end.hour == 20
    assert rules[0].active_hours.end.minute == 0


def test_invalid_active_hours_format_raises_error(tmp_path):
    """Invalid active-hour timestamps should fail validation."""
    config = {
        "alert_rules": [
            {
                "rule_id": "daylight_only",
                "name": "Daylight Only",
                "description": "Light below {threshold} lux",
                "severity": "warning",
                "evaluation_stage": "processed",
                "source": "light_intensity",
                "condition": {
                    "type": "threshold",
                    "operator": "<",
                    "threshold": 1000.0,
                },
                "active_hours": {"start": "8:00", "end": "20:00"},
                "persistence_count": 1,
                "cooldown_seconds": 60,
            }
        ]
    }
    config_file = tmp_path / "invalid_active_hours.yml"
    config_file.write_text(yaml.dump(config))

    with pytest.raises(ValueError, match="Invalid active hours"):
        build_alert_rule_manager(str(config_file))
