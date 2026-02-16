"""Actuator policy management.

Loads and resolves actuator policies from a YAML configuration file.
Policies define constraints like maximum duration, cooldown periods,
and allowed commands for each actuator type and plant.
"""

import yaml
from pathlib import Path
from typing import Optional

from dt.communication.adapters import load
from dt.communication.dataclasses.controller import ActuatorConfig, ActuatorConfigSet
from dt.utils import Config, get_logger

logger = get_logger(__name__)


class PolicyManager:
    """Manages actuator policies loaded from configuration."""

    def __init__(self, config_path: str = Config.ACTUATOR_POLICIES_PATH):
        self.config_path = Path(config_path)
        self.config: Optional[ActuatorConfigSet] = None
        self.load_policies()

    def load_policies(self) -> None:
        """Load policies from the YAML configuration file."""
        if not self.config_path.exists():
            logger.warning(f"Policy config not found at {self.config_path}, using defaults.")
            self.config = ActuatorConfigSet()
            return

        try:
            with open(self.config_path, "r") as f:
                data = yaml.safe_load(f)
            self.config = load("generic", ActuatorConfigSet, data)
            logger.info(f"Loaded actuator policies from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load policies: {e}")
            self.config = ActuatorConfigSet()

    def resolve(self, plant_id: int, actuator_name: str) -> ActuatorConfig:
        """Resolve the effective policy for a given plant and actuator.

        The resolution order is:
        1. Hardcoded system defaults (fallback)
        2. Global defaults from config
        3. Actuator-specific defaults from config
        4. Plant-specific actuator overrides from config

        Parameters
        ----------
        plant_id : int
            The ID of the plant.
        actuator_name : str
            The name (type) of the actuator (e.g., "pump", "light").

        Returns
        -------
        ActuatorPolicy
            The resolved policy.
        """
        # Base policy with hardcoded defaults to ensure we always return something valid
        base = ActuatorConfig(
            max_duration_seconds=30.0,
            min_cooldown_seconds=10.0,
            allow_overlap=False,
            allowed_commands=["ON", "OFF"],
        )

        if not self.config:
            return base

        # 1. Merge global defaults
        base = self._merge(base, self.config.defaults)

        # 2. Merge actuator-specific defaults
        if actuator_name in self.config.actuators:
            base = self._merge(base, self.config.actuators[actuator_name])

        # 3. Merge plant-specific overrides
        plant_key = str(plant_id)
        if plant_key in self.config.plants:
            plant_config = self.config.plants[plant_key]
            if actuator_name in plant_config.actuators:
                base = self._merge(base, plant_config.actuators[actuator_name])

        return base

    def _merge(self, base: ActuatorConfig, override: ActuatorConfig) -> ActuatorConfig:
        """Merge override into base, preferring non-None values from override."""
        return ActuatorConfig(
            max_duration_seconds=override.max_duration_seconds
            if override.max_duration_seconds is not None
            else base.max_duration_seconds,
            min_cooldown_seconds=override.min_cooldown_seconds
            if override.min_cooldown_seconds is not None
            else base.min_cooldown_seconds,
            allow_overlap=override.allow_overlap
            if override.allow_overlap is not None
            else base.allow_overlap,
            allowed_commands=override.allowed_commands
            if override.allowed_commands is not None
            else base.allowed_commands,
        )
