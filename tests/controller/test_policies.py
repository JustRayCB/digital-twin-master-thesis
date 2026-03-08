"""Tests for actuator policy resolution."""

from dt.communication.dataclasses.controller import ActuatorConfig
from dt.controller.policies import PolicyManager


def test_policy_resolution_falls_back_to_defaults(policy_config_path: str) -> None:
    """Return default policy for unknown actuators.

    Parameters
    ----------
    policy_config_path : str
        Path to the policy configuration file.

    Returns
    -------
    None
        Assertions fail if defaults stop applying.
    """
    manager = PolicyManager(config_path=policy_config_path)

    policy = manager.resolve(plant_id=2, actuator_name="mister")

    assert policy.max_duration_seconds == 30
    assert policy.min_cooldown_seconds == 0
    assert policy.allow_overlap is False
