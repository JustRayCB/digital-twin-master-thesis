"""Tests for alert rule evaluation engine."""

import pytest

from dt.alerts.config.alert_rule import (AlertCondition, AlertRule,
                                         ConditionType, EvaluationStage,
                                         SeverityLevel)
from dt.alerts.engine.evaluator import RuleEvaluator
from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.topics import Topics


@pytest.fixture
def sample_processed_data():
    """Create sample processed sensor data for testing."""
    return ProcessedSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=1234567890.0,
        value=38.5,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-corr-123",
        flags={
            ValidationFlag.VALID: True,
            ValidationFlag.RANGE: False,
            ValidationFlag.RATE_OF_CHANGE: False,
            ValidationFlag.STUCK: False,
        },
        dq_score=0.95,
        imputed=False,
    )


@pytest.fixture
def threshold_rule():
    """Create a threshold-based alert rule."""
    return AlertRule(
        rule_id="temp_high",
        name="High Temperature Alert",
        description="Temperature exceeds {threshold}°C (actual: {value}°C)",
        severity=SeverityLevel.WARNING,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="temperature",
        condition=AlertCondition(
            type=ConditionType.THRESHOLD,
            params={"operator": ">", "threshold": 35.0},
        ),
        persistence_count=2,
        cooldown_seconds=300,
    )


@pytest.fixture
def range_rule():
    """Create a range-based alert rule."""
    return AlertRule(
        rule_id="moisture_range",
        name="Moisture Out of Range",
        description="Soil moisture outside safe range [{min_value}, {max_value}]% (actual: {value}%)",
        severity=SeverityLevel.CRITICAL,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="soil_moisture",
        condition=AlertCondition(
            type=ConditionType.RANGE,
            params={"min_value": 20.0, "max_value": 80.0},
        ),
        persistence_count=3,
        cooldown_seconds=600,
    )


@pytest.fixture
def dq_score_rule():
    """Create a data quality score rule."""
    return AlertRule(
        rule_id="dq_low",
        name="Low Data Quality",
        description="Data quality score {dq_score} below threshold {threshold}",
        severity=SeverityLevel.INFO,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="*",  # Apply to all sources
        condition=AlertCondition(
            type=ConditionType.DQ_SCORE,
            params={"threshold": 0.7},
        ),
        persistence_count=1,
        cooldown_seconds=120,
    )


@pytest.fixture
def validation_flag_rule():
    """Create a validation flag rule."""
    return AlertRule(
        rule_id="range_violation",
        name="Range Validation Failed",
        description="Sensor reading failed range validation",
        severity=SeverityLevel.WARNING,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="humidity",
        condition=AlertCondition(
            type=ConditionType.VALIDATION_FLAG,
            params={"flag": "range_violation", "expected": True},
        ),
        persistence_count=1,
        cooldown_seconds=180,
    )


@pytest.mark.parametrize(
    "value,threshold,operator,should_trigger",
    [
        (40.0, 35.0, ">", True),  # Above threshold
        (30.0, 35.0, ">", False),  # Below threshold
        (35.0, 35.0, ">", False),  # Equal (not greater)
        (30.0, 35.0, "<", True),  # Below threshold
        (40.0, 35.0, "<", False),  # Above threshold
        (35.0, 35.0, ">=", True),  # Equal or greater
        (40.0, 35.0, ">=", True),  # Greater
        (30.0, 35.0, ">=", False),  # Less
        (35.0, 35.0, "<=", True),  # Equal or less
        (30.0, 35.0, "<=", True),  # Less
        (40.0, 35.0, "<=", False),  # Greater
        (35.0, 35.0, "==", True),  # Equal
        (30.0, 35.0, "==", False),  # Not
        (40.0, 35.0, "!=", True),  # Not equal
        (35.0, 35.0, "!=", False),  # Equal
    ],
)
def test_threshold_condition_evaluation(value, threshold, operator, should_trigger):
    """Test threshold condition with various operators."""
    rule = AlertRule(
        rule_id="test_threshold",
        name="Test Threshold",
        description="Value {value} vs threshold {threshold}",
        severity=SeverityLevel.WARNING,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="temperature",
        condition=AlertCondition(
            type=ConditionType.THRESHOLD,
            params={"operator": operator, "threshold": threshold},
        ),
        persistence_count=1,
        cooldown_seconds=60,
    )

    data = ProcessedSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=1234567890.0,
        value=value,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-corr-123",
        flags={ValidationFlag.VALID: True},
        dq_score=0.95,
        imputed=False,
    )

    evaluator = RuleEvaluator([rule])
    candidates = evaluator.evaluate(data)

    if should_trigger:
        assert len(candidates) == 1
        assert candidates[0].rule_id == "test_threshold"
        assert candidates[0].severity == SeverityLevel.WARNING
        assert candidates[0].source == "temperature"
        assert candidates[0].correlation_id == "test-corr-123"
        assert str(value) in candidates[0].message
        assert str(threshold) in candidates[0].message
    else:
        assert len(candidates) == 0


@pytest.mark.parametrize(
    "value,min_val,max_val,should_trigger",
    [
        (50.0, 20.0, 80.0, False),  # Within range
        (15.0, 20.0, 80.0, True),  # Below min
        (85.0, 20.0, 80.0, True),  # Above max
        (20.0, 20.0, 80.0, False),  # At min boundary
        (80.0, 20.0, 80.0, False),  # At max boundary
        (50.0, None, 80.0, False),  # Within range, no min
        (90.0, None, 80.0, True),  # Above max, no min
        (15.0, 20.0, None, True),  # Below min, no max
        (50.0, 20.0, None, False),  # Above min, no max
    ],
)
def test_range_condition_evaluation(value, min_val, max_val, should_trigger):
    """Test range condition with various boundaries."""
    rule = AlertRule(
        rule_id="test_range",
        name="Test Range",
        description="Value {value} outside range [{min_value}, {max_value}]",
        severity=SeverityLevel.CRITICAL,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="soil_moisture",
        condition=AlertCondition(
            type=ConditionType.RANGE,
            params={"min_value": min_val, "max_value": max_val},
        ),
        persistence_count=1,
        cooldown_seconds=60,
    )

    data = ProcessedSensorData(
        plant_id=1,
        sensor_id=102,
        timestamp=1234567890.0,
        value=value,
        unit="Percent",
        topic=Topics.SOIL_MOISTURE,
        correlation_id="test-corr-456",
        flags={ValidationFlag.VALID: True},
        dq_score=0.95,
        imputed=False,
    )

    evaluator = RuleEvaluator([rule])
    candidates = evaluator.evaluate(data)

    if should_trigger:
        assert len(candidates) == 1
        assert candidates[0].rule_id == "test_range"
    else:
        assert len(candidates) == 0


@pytest.mark.parametrize(
    "dq_score,threshold,should_trigger",
    [
        (0.95, 0.7, False),  # Above threshold
        (0.65, 0.7, True),  # Below threshold
        (0.7, 0.7, False),  # At threshold (not below)
        (0.5, 0.8, True),  # Well below
        (1.0, 0.9, False),  # Perfect score
    ],
)
def test_dq_score_condition_evaluation(dq_score, threshold, should_trigger):
    """Test data quality score condition."""
    rule = AlertRule(
        rule_id="test_dq",
        name="Test DQ Score",
        description="DQ score {dq_score} below {threshold}",
        severity=SeverityLevel.INFO,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="*",
        condition=AlertCondition(
            type=ConditionType.DQ_SCORE,
            params={"threshold": threshold},
        ),
        persistence_count=1,
        cooldown_seconds=60,
    )

    data = ProcessedSensorData(
        plant_id=1,
        sensor_id=103,
        timestamp=1234567890.0,
        value=25.5,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-corr-789",
        flags={ValidationFlag.VALID: True},
        dq_score=dq_score,
        imputed=False,
    )

    evaluator = RuleEvaluator([rule])
    candidates = evaluator.evaluate(data)

    if should_trigger:
        assert len(candidates) == 1
        assert candidates[0].rule_id == "test_dq"
        assert str(dq_score) in candidates[0].message
    else:
        assert len(candidates) == 0


@pytest.mark.parametrize(
    "flag_value,expected,should_trigger",
    [
        (True, True, True),  # Flag is set as expected
        (False, True, False),  # Flag not set, expected set
        (True, False, False),  # Flag set, expected not set
        (False, False, True),  # Flag not set as expected
    ],
)
def test_validation_flag_condition_evaluation(flag_value, expected, should_trigger):
    """Test validation flag condition."""
    rule = AlertRule(
        rule_id="test_flag",
        name="Test Validation Flag",
        description="Validation flag check",
        severity=SeverityLevel.WARNING,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="humidity",
        condition=AlertCondition(
            type=ConditionType.VALIDATION_FLAG,
            params={"flag": "range_violation", "expected": expected},
        ),
        persistence_count=1,
        cooldown_seconds=60,
    )

    data = ProcessedSensorData(
        plant_id=1,
        sensor_id=104,
        timestamp=1234567890.0,
        value=55.0,
        unit="Percent",
        topic=Topics.HUMIDITY,
        correlation_id="test-corr-999",
        flags={
            ValidationFlag.VALID: not flag_value,
            ValidationFlag.RANGE: flag_value,
        },
        dq_score=0.85,
        imputed=False,
    )

    evaluator = RuleEvaluator([rule])
    candidates = evaluator.evaluate(data)

    if should_trigger:
        assert len(candidates) == 1
        assert candidates[0].rule_id == "test_flag"
    else:
        assert len(candidates) == 0


def test_rule_only_evaluates_matching_source(threshold_rule, sample_processed_data):
    """Test that rules only apply to matching sources."""
    # Rule is for "temperature", data is for temperature
    evaluator = RuleEvaluator([threshold_rule])
    candidates = evaluator.evaluate(sample_processed_data)
    assert len(candidates) == 1  # Should trigger (38.5 > 35.0)

    # Change data to different sensor type
    different_data = ProcessedSensorData(
        plant_id=1,
        sensor_id=102,
        timestamp=1234567890.0,
        value=38.5,
        unit="Percent",
        topic=Topics.HUMIDITY,  # Different topic
        correlation_id="test-corr-123",
        flags={ValidationFlag.VALID: True},
        dq_score=0.95,
        imputed=False,
    )

    candidates = evaluator.evaluate(different_data)
    assert len(candidates) == 0  # Should not trigger (wrong source)


def test_wildcard_source_matches_all_topics(dq_score_rule):
    """Test that wildcard source '*' matches all sensor topics."""
    evaluator = RuleEvaluator([dq_score_rule])

    # Low DQ score should trigger regardless of topic
    low_dq_data = ProcessedSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=1234567890.0,
        value=25.0,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-corr-temp",
        flags={ValidationFlag.VALID: True},
        dq_score=0.65,  # Below 0.7 threshold
        imputed=False,
    )

    candidates = evaluator.evaluate(low_dq_data)
    assert len(candidates) == 1
    assert candidates[0].source == "temperature"

    # Test with different topic
    low_dq_humidity = ProcessedSensorData(
        plant_id=1,
        sensor_id=102,
        timestamp=1234567890.0,
        value=55.0,
        unit="Percent",
        topic=Topics.HUMIDITY,
        correlation_id="test-corr-hum",
        flags={ValidationFlag.VALID: True},
        dq_score=0.60,  # Below 0.7 threshold
        imputed=False,
    )

    candidates = evaluator.evaluate(low_dq_humidity)
    assert len(candidates) == 1
    assert candidates[0].source == "humidity"


def test_evaluator_returns_empty_list_when_no_rules_match():
    """Test that evaluator returns empty list when no rules trigger."""
    rule = AlertRule(
        rule_id="temp_high",
        name="High Temperature",
        description="Temperature too high",
        severity=SeverityLevel.WARNING,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="temperature",
        condition=AlertCondition(
            type=ConditionType.THRESHOLD,
            params={"operator": ">", "threshold": 50.0},
        ),
        persistence_count=1,
        cooldown_seconds=60,
    )

    data = ProcessedSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=1234567890.0,
        value=25.0,  # Well below threshold
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-corr-123",
        flags={ValidationFlag.VALID: True},
        dq_score=0.95,
        imputed=False,
    )

    evaluator = RuleEvaluator([rule])
    candidates = evaluator.evaluate(data)

    assert candidates == []


def test_evaluator_handles_multiple_rules(threshold_rule, dq_score_rule):
    """Test that evaluator can apply multiple rules to same data."""
    # Data that triggers both rules
    data = ProcessedSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=1234567890.0,
        value=38.5,  # Above threshold
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-corr-123",
        flags={ValidationFlag.VALID: True},
        dq_score=0.65,  # Below DQ threshold
        imputed=False,
    )

    evaluator = RuleEvaluator([threshold_rule, dq_score_rule])
    candidates = evaluator.evaluate(data)

    assert len(candidates) == 2
    rule_ids = {c.rule_id for c in candidates}
    assert rule_ids == {"temp_high", "dq_low"}


def test_candidate_alert_contains_payload_snapshot(threshold_rule, sample_processed_data):
    """Test that candidate alert includes relevant payload data."""
    evaluator = RuleEvaluator([threshold_rule])
    candidates = evaluator.evaluate(sample_processed_data)

    assert len(candidates) == 1
    candidate = candidates[0]

    # Verify payload contains key data
    assert candidate.payload["value"] == 38.5
    assert candidate.payload["sensor_id"] == 101
    assert candidate.payload["timestamp"] == 1234567890.0
    assert candidate.payload["dq_score"] == 0.95
    assert "flags" in candidate.payload


def test_unsupported_condition_type_raises_not_implemented():
    """Test that unsupported condition types raise NotImplementedError."""
    # This would be a future condition type not yet implemented
    rule = AlertRule(
        rule_id="test_unsupported",
        name="Unsupported Condition",
        description="Test",
        severity=SeverityLevel.INFO,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="temperature",
        condition=AlertCondition(
            type=ConditionType.THRESHOLD,  # We'll manually set an invalid type
            params={},
        ),
        persistence_count=1,
        cooldown_seconds=60,
    )
    # Manually override to simulate unsupported type
    rule.condition.type = "unsupported_type"  # type: ignore

    data = ProcessedSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=1234567890.0,
        value=25.0,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-corr-123",
        flags={ValidationFlag.VALID: True},
        dq_score=0.95,
        imputed=False,
    )

    evaluator = RuleEvaluator([rule])

    with pytest.raises(NotImplementedError, match="Condition type.*not supported"):
        evaluator.evaluate(data)
