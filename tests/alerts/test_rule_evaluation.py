"""Tests for alert rule evaluation engine."""

import pytest

from dt.alerts.evaluator import RuleEvaluator
from dt.alerts.rules import AlertCondition, AlertRule, ConditionType, EvaluationStage, SeverityLevel
from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.alerts.alert_record import AlertDefinition
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.topics import Topics

pytestmark = [pytest.mark.requires_kafka, pytest.mark.requires_timescale]


@pytest.fixture
def validation_flag_rule():
    """Create a validation flag rule.

    Returns
    -------
    AlertRule
        Validation flag alert rule.
    """
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
    """Test threshold condition with various operators.

    Parameters
    ----------
    value : float
        Sensor reading value.
    threshold : float
        Threshold to compare against.
    operator : str
        Operator used by the rule.
    should_trigger : bool
        Expected evaluation outcome.

    Returns
    -------
    None
        The assertions raise if threshold evaluation regresses.
    """
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
        definition, event = candidates[0]
        assert isinstance(definition, AlertDefinition)
        assert event.alert_key == "test_threshold:temperature"
        assert event.severity == SeverityLevel.WARNING
        assert event.correlation_id == "test-corr-123"
        assert str(value) in event.message
        assert str(threshold) in event.message
        assert definition.alert_key == event.alert_key
        assert definition.plant_id == event.plant_id
        assert definition.sensor_id == data.sensor_id
        assert definition.source == "temperature"
        assert definition.rule_id == "test_threshold"
        assert definition.rule_name == "Test Threshold"
        assert definition.kind == AlertType.SENSOR
        assert definition.persistence_count == 1
        assert definition.cooldown_seconds == 60
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
    """Test range condition with various boundaries.

    Parameters
    ----------
    value : float
        Sensor reading value.
    min_val : float | None
        Minimum acceptable value.
    max_val : float | None
        Maximum acceptable value.
    should_trigger : bool
        Expected evaluation outcome.

    Returns
    -------
    None
        The assertions raise if range evaluation regresses.
    """
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
        definition, event = candidates[0]
        assert event.alert_key == "test_range:soil_moisture"
        assert event.correlation_id == "test-corr-456"
        assert definition.alert_key == event.alert_key
        assert definition.source == "soil_moisture"
        assert definition.sensor_id == data.sensor_id
        assert definition.persistence_count == rule.persistence_count
        assert definition.cooldown_seconds == rule.cooldown_seconds
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
    """Test data quality score condition.

    Parameters
    ----------
    dq_score : float
        Data quality score to evaluate.
    threshold : float
        Threshold for the rule.
    should_trigger : bool
        Expected evaluation outcome.

    Returns
    -------
    None
        The assertions raise if DQ evaluation regresses.
    """
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
        definition, event = candidates[0]
        assert event.alert_key == f"test_dq:{data.topic.short_name}"
        assert str(dq_score) in event.message
        assert definition.persistence_count == 1
        assert definition.cooldown_seconds == 60
        assert definition.source == data.topic.short_name
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
    """Test validation flag condition.

    Parameters
    ----------
    flag_value : bool
        Flag value present on the reading.
    expected : bool
        Expected flag value per the rule.
    should_trigger : bool
        Expected evaluation outcome.

    Returns
    -------
    None
        The assertions raise if flag evaluation regresses.
    """
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
        definition, event = candidates[0]
        assert event.alert_key == "test_flag:humidity"
        assert definition.persistence_count == 1
        assert definition.cooldown_seconds == 60
        assert definition.source == "humidity"
    else:
        assert len(candidates) == 0


def test_rule_only_evaluates_matching_source(threshold_rule, sample_processed_data):
    """Test that rules only apply to matching sources.

    Parameters
    ----------
    threshold_rule : AlertRule
        Rule that targets temperature readings.
    sample_processed_data : ProcessedSensorData
        Processed reading fixture.

    Returns
    -------
    None
        The assertions raise if source matching regresses.
    """
    # Rule is for "temperature", data is for temperature
    evaluator = RuleEvaluator([threshold_rule])
    candidates = evaluator.evaluate(sample_processed_data)
    assert len(candidates) == 1  # Should trigger (38.5 > 35.0)
    _, event = candidates[0]
    assert event.alert_key == "temp_high:temperature"
    assert event.reading.topic == Topics.TEMPERATURE

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


def test_wildcard_source_matches_all_topics(dq_rule):
    """Test that wildcard source '*' matches all sensor topics.

    Parameters
    ----------
    dq_rule : AlertRule
        Rule using wildcard source.

    Returns
    -------
    None
        The assertions raise if wildcard matching regresses.
    """
    evaluator = RuleEvaluator([dq_rule])

    # Low DQ score should trigger regardless of topic
    # shared dq_rule has threshold 0.5
    low_dq_data = ProcessedSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=1234567890.0,
        value=25.0,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-corr-temp",
        flags={ValidationFlag.VALID: True},
        dq_score=0.45,  # Below 0.5 threshold
        imputed=False,
    )

    candidates = evaluator.evaluate(low_dq_data)
    assert len(candidates) == 1
    _, event = candidates[0]
    assert event.reading.topic == Topics.TEMPERATURE
    assert event.alert_key == "dq_low:temperature"

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
        dq_score=0.40,  # Below 0.5 threshold
        imputed=False,
    )

    candidates = evaluator.evaluate(low_dq_humidity)
    assert len(candidates) == 1
    _, event = candidates[0]
    assert event.reading.topic == Topics.HUMIDITY
    assert event.alert_key == "dq_low:humidity"


def test_evaluator_returns_empty_list_when_no_rules_match():
    """Test that evaluator returns empty list when no rules trigger.

    Returns
    -------
    None
        The assertions raise if evaluation results regress.
    """
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


def test_evaluator_handles_multiple_rules(threshold_rule, dq_rule):
    """Test that evaluator can apply multiple rules to same data.

    Parameters
    ----------
    threshold_rule : AlertRule
        Threshold rule for evaluation.
    dq_rule : AlertRule
        DQ score rule for evaluation.

    Returns
    -------
    None
        The assertions raise if multi-rule evaluation regresses.
    """
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
        dq_score=0.45,  # Below DQ threshold (0.5)
        imputed=False,
    )

    evaluator = RuleEvaluator([threshold_rule, dq_rule])
    candidates = evaluator.evaluate(data)

    assert len(candidates) == 2
    rule_ids = {event.alert_key.split(":", 1)[0] for _, event in candidates}
    assert rule_ids == {"temp_high", "dq_low"}


def test_sensor_alert_event_contains_payload_snapshot(threshold_rule, sample_processed_data):
    """Test that sensor alert event includes sensor reading data.

    Parameters
    ----------
    threshold_rule : AlertRule
        Rule used to generate the event.
    sample_processed_data : ProcessedSensorData
        Processed reading fixture.

    Returns
    -------
    None
        The assertions raise if payload snapshots regress.
    """
    evaluator = RuleEvaluator([threshold_rule])
    candidates = evaluator.evaluate(sample_processed_data)

    assert len(candidates) == 1
    definition, event = candidates[0]

    # Verify sensor_reading contains key data
    assert event.reading.value == 38.0
    assert event.reading.sensor_id == 101
    assert event.reading.timestamp == 1234567890.0
    assert event.reading.dq_score == 0.95
    assert event.reading.flags is not None
    assert definition.persistence_count == threshold_rule.persistence_count
    assert definition.cooldown_seconds == threshold_rule.cooldown_seconds


def test_unsupported_condition_type_raises_not_implemented():
    """Test that unsupported condition types raise NotImplementedError.

    Returns
    -------
    None
        The assertions raise if error handling regresses.
    """
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
