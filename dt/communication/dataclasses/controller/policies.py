from dataclasses import dataclass, field
from typing import Dict

from dt.communication.dataclasses.controller.actuators import ActuatorConfig


@dataclass
class PlantActuatorConfig:
    """Plant-scoped actuator policy overrides.

    Attributes
    ----------
    actuators : Dict[str, ActuatorConfig]
        Mapping of actuator name to the policy override for one plant.
    """

    actuators: Dict[str, ActuatorConfig] = field(default_factory=dict)


@dataclass
class ActuatorConfigSet:
    """Top-level actuator policy configuration model.

    Resolution order is defined by controller policy logic and typically uses:
    defaults -> actuator-specific values -> plant-specific overrides.

    Attributes
    ----------
    defaults : ActuatorConfig
        Baseline values applied to all actuators when no override is defined.
    actuators : Dict[str, ActuatorConfig]
        Global per-actuator overrides keyed by actuator name.
    plants : Dict[str, PlantActuatorConfig]
        Plant-specific overrides keyed by plant identifier string.
    """

    defaults: ActuatorConfig = field(default_factory=ActuatorConfig)
    actuators: Dict[str, ActuatorConfig] = field(default_factory=dict)
    plants: Dict[str, PlantActuatorConfig] = field(default_factory=dict)
