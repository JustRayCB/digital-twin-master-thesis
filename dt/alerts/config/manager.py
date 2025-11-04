"""Alert rule configuration manager.

Manages loading and merging of alert rules from YAML configuration.
"""

from typing import Any

import yaml

from dt.alerts.config.alert_rule import AlertRule


class AlertRuleManager:
    """Manages alert rule configuration loading and overrides.

    This class handles loading alert rules from YAML files, validating
    rule definitions, and merging runtime overrides with base rules.
    """

    def __init__(self, alert_rules: list[AlertRule]) -> None:
        """Initialize the alert rule manager.

        Parameters
        ----------
        alert_rules : list[AlertRule]
            List of base alert rules to manage.
        """
        self._rules: list[AlertRule] = alert_rules

    @classmethod
    def load(cls, config_path: str) -> "AlertRuleManager":
        """Load and parse alert rules from configuration file.

        Returns
        -------
        AlertRuleManager
            Instance of AlertRuleManager with loaded rules.

        Raises
        ------
        ValueError
            If configuration is malformed or contains invalid values.
        FileNotFoundError
            If configuration file does not exist.
        """
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise ValueError(
                f"Invalid alert rules configuration: expected YAML mapping, "
                f"got {type(config).__name__}"
            )

        rules = [AlertRule.from_dict(rule_data) for rule_data in config.get("alert_rules", [])]
        return cls(rules)

    def merge_overrides(self, overrides: dict[str, dict[str, Any]]) -> list[AlertRule]:
        """Merge runtime overrides with loaded rules.

        Parameters
        ----------
        overrides : dict[str, dict[str, Any]]
            Dictionary mapping rule_id to override parameters.

        Returns
        -------
        list[AlertRule]
            List of rules with overrides applied and new rules added.
        """
        rules_dict = {rule.rule_id: rule for rule in self._rules}

        for rule_id, override_data in overrides.items():
            if rule_id in rules_dict:
                rules_dict[rule_id] = self._apply_override(rules_dict[rule_id], override_data)
            else:
                rules_dict[rule_id] = AlertRule.from_dict(override_data)

        return list(rules_dict.values())

    def _apply_override(self, base_rule: AlertRule, override_data: dict[str, Any]) -> AlertRule:
        """Apply override parameters to a base rule."""
        return base_rule.override(override_data)

    @property
    def rules(self) -> list[AlertRule]:
        """Get list of managed alert rules."""
        return self._rules

    def __len__(self) -> int:
        """Get number of managed alert rules."""
        return len(self._rules)


def build_alert_rule_manager(config_path: str) -> AlertRuleManager:
    """Load alert rules from YAML configuration file.

    Convenience function that creates an AlertRuleManager and loads rules.

    Parameters
    ----------
    config_path : str
        Path to the YAML configuration file.

    Returns
    -------
    AlertRuleManager
        Instance of AlertRuleManager with loaded rules.
    """

    return AlertRuleManager.load(config_path)
