"""Alert rule evaluator.

Evaluates configured alert rules against processed sensor payloads.
"""

from dt.alerts.config.alert_rule import (AlertRule, ConditionType,
                                         EvaluationStage)
from dt.communication.dataclasses.alerts import CandidateAlert
from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag


class RuleEvaluator:
    """Evaluates alert rules against processed sensor data.

    Attributes
    ----------
    rules : list[AlertRule]
        List of alert rules to evaluate.
    """

    def __init__(self, rules: list[AlertRule]) -> None:
        """Initialize the rule evaluator.

        Parameters
        ----------
        rules : list[AlertRule]
            List of alert rules to evaluate.
        """
        self.rules = rules

    def evaluate(self, payload: ProcessedSensorData) -> list[CandidateAlert]:
        """Evaluate all applicable rules against a processed sensor payload.

        Parameters
        ----------
        payload : ProcessedSensorData
            The processed sensor data to evaluate.

        Returns
        -------
        list[CandidateAlert]
            List of candidate alerts for rules that triggered.
        """
        candidates = []
        source = payload.topic.short_name

        for rule in self.rules:
            # Skip if evaluation stage doesn't match
            if rule.evaluation_stage != EvaluationStage.PROCESSED:
                continue

            # Skip if source doesn't match (unless wildcard)
            if rule.source != "*" and rule.source != source:
                continue

            # Evaluate the condition
            if self._evaluate_condition(rule, payload):
                candidate = self._create_candidate_alert(rule, payload, source)
                candidates.append(candidate)

        return candidates

    def _evaluate_condition(self, rule: AlertRule, payload: ProcessedSensorData) -> bool:
        """Evaluate a single rule's condition against payload.

        Parameters
        ----------
        rule : AlertRule
            The rule to evaluate.
        payload : ProcessedSensorData
            The processed sensor data.

        Returns
        -------
        bool
            True if condition is met, False otherwise.

        Raises
        ------
        NotImplementedError
            If the condition type is not supported.
        """
        condition = rule.condition

        if condition.type == ConditionType.THRESHOLD:
            return self._evaluate_threshold(condition.params, payload.value)

        elif condition.type == ConditionType.RANGE:
            return self._evaluate_range(condition.params, payload.value)

        elif condition.type == ConditionType.DQ_SCORE:
            return self._evaluate_dq_score(condition.params, payload.dq_score)

        elif condition.type == ConditionType.VALIDATION_FLAG:
            return self._evaluate_validation_flag(condition.params, payload.flags)

        else:
            raise NotImplementedError(
                f"Condition type '{condition.type}' is not supported. "
                f"Supported types: {', '.join(c.value for c in ConditionType)}"
            )

    def _evaluate_threshold(self, params: dict, value: float) -> bool:
        """Evaluate a threshold condition.

        Parameters
        ----------
        params : dict
            Condition parameters (operator, threshold).
        value : float
            The sensor value to check.

        Returns
        -------
        bool
            True if threshold condition is met.
        """
        operator = params["operator"]
        threshold = params["threshold"]

        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        elif operator == "!=":
            return value != threshold
        else:
            return False

    def _evaluate_range(self, params: dict, value: float) -> bool:
        """Evaluate a range condition.

        Parameters
        ----------
        params : dict
            Condition parameters (min_value, max_value).
        value : float
            The sensor value to check.

        Returns
        -------
        bool
            True if value is outside the specified range.
        """
        min_value = params.get("min_value")
        max_value = params.get("max_value")

        # Check if value is below minimum (if specified)
        if min_value is not None and value < min_value:
            return True

        # Check if value is above maximum (if specified)
        if max_value is not None and value > max_value:
            return True

        return False

    def _evaluate_dq_score(self, params: dict, dq_score: float) -> bool:
        """Evaluate a data quality score condition.

        Parameters
        ----------
        params : dict
            Condition parameters (threshold).
        dq_score : float
            The data quality score to check.

        Returns
        -------
        bool
            True if DQ score is below threshold.
        """
        threshold = params["threshold"]
        return dq_score < threshold

    def _evaluate_validation_flag(self, params: dict, flags: dict[ValidationFlag, bool]) -> bool:
        """Evaluate a validation flag condition.

        Parameters
        ----------
        params : dict
            Condition parameters (flag, expected).
        flags : dict[ValidationFlag, bool]
            The validation flags from processed data.

        Returns
        -------
        bool
            True if flag matches expected value.
        """
        flag_name = params["flag"]
        expected = params["expected"]

        # Convert string flag name to ValidationFlag enum
        try:
            flag_enum = ValidationFlag(flag_name)
        except ValueError:
            # If flag name is invalid, condition doesn't match
            return False

        # Check if flag value matches expected
        actual = flags.get(flag_enum, False)
        return actual == expected

    def _create_candidate_alert(
        self, rule: AlertRule, payload: ProcessedSensorData, source: str
    ) -> CandidateAlert:
        """Create a candidate alert from a triggered rule.

        Parameters
        ----------
        rule : AlertRule
            The rule that triggered.
        payload : ProcessedSensorData
            The processed sensor data.
        source : str
            The topic short name.

        Returns
        -------
        CandidateAlert
            The candidate alert.
        """
        # Generate alert_id for rule-based alerts
        alert_id = f"{rule.rule_id}:{source}"

        # Prepare values for message formatting
        format_values = {
            **payload.to_dict(),  # Include payload data
            **rule.condition.params,  # Include condition params (threshold, min_value, etc.)
        }

        # Format the message
        message = rule.description.format(**format_values)

        return CandidateAlert(
            alert_id=alert_id,
            rule_id=rule.rule_id,
            source=source,
            severity=rule.severity,
            message=message,
            correlation_id=payload.correlation_id,
            payload=payload.to_dict(),
            persistence_count=rule.persistence_count,
            cooldown_seconds=rule.cooldown_seconds,
        )
