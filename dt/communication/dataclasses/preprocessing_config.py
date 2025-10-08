from dataclasses import dataclass
from typing import Dict, Optional

import yaml

from dt.utils import Config


@dataclass
class WindowDefaults:
    """Default rolling window sizes for different checks.

    Attributes
    ----------
    small_sec : Small window size in seconds for quick checks.
    medium_sec : Medium window size in seconds for standard checks. e.g., for rate of change.
    big_sec : Large window size in seconds for long-term checks. e.g., for stuck detection.

    """

    small_sec: int
    medium_sec: int
    big_sec: int


@dataclass
class ScoringWeights:
    """Default weights for Data Quality scoring.
    Data quality checks include range, rate of change, and stuck value detection.
    Each weight represents the importance of the corresponding check in the overall score.
    Increasing a weight increases the influence of that check on the final score.

    Attributes
    ----------
    range_ok : Weight for range check.
    roc_ok : Weight for rate of change check.
    stuck_ok : Weight for stuck value check.

    """

    range_ok: float
    roc_ok: float
    stuck_ok: float


@dataclass
class ScoringDefaults:
    """Default scoring configuration for Data Quality checks.
    Later, this could be extended to include thresholds or other parameters.

    Attributes
    ----------
    weights : Weights for different data quality checks.

    """

    weights: ScoringWeights


@dataclass
class Defaults:
    """Default configuration for sensor validation.

    Attributes
    ----------
    windows : WindowDefaults
        Default rolling window sizes for different checks.
    scoring : ScoringDefaults
        Default scoring configuration for Data Quality checks.

    """

    windows: WindowDefaults
    scoring: ScoringDefaults


# INDIVIDUAL SENSORS CONFIGURATION


@dataclass
class RangeConfig:
    """Configuration for valid sensor value range.

    Attributes
    ----------
    min : Minimum valid value.
    max : Maximum valid value.

    """

    min: float
    max: float


@dataclass
class RocProfile:
    """Configuration for a rate of change (RoC) profile.
    This defines the maximum allowed rate of change for a sensor value within a minute.

    Attributes
    ----------
    max_per_minute : Maximum allowed rate of change per minute.

    """

    max_per_minute: float


@dataclass
class RocConfig:
    """Configuration for rate of change (RoC) checks.
    This includes multiple profiles for different scenarios and an optional active profile.
    If no active profile is set, the max_per_minute attribute is used as a default limit.

    Attributes
    ----------
    max_per_minute : Default maximum allowed rate of change per minute if no profile is active.
    profiles : Dictionary of named RoC profiles. e.g Indoor, Outdoor, etc.
    active_profile : Name of the currently active RoC profile. If None, max_per_minute is used.

    """

    max_per_minute: Optional[float]
    profiles: Dict[str, RocProfile]
    active_profile: Optional[str]

    @property
    def active_max_per_minute(self) -> Optional[float]:
        """Get the maximum allowed rate of change per minute for the active profile.
        If no active profile is set, return the default max_per_minute.

        Returns
        -------
        float or None
            Maximum allowed rate of change per minute.
        """
        if self.active_profile and self.active_profile in self.profiles:
            return self.profiles[self.active_profile].max_per_minute
        return self.max_per_minute


@dataclass
class StuckConfig:
    """Configuration for stuck value detection.
    This defines the maximum duration a sensor value can remain unchanged before being flagged as stuck.

    Attributes
    ----------
    max_flat_seconds : Maximum duration in seconds a sensor value can remain unchanged.

    """

    max_flat_seconds: int


@dataclass
class SensorConfig:
    """Configuration for an individual sensor's validation parameters.


    Attributes
    ----------
    units : Units of measurement for the sensor (e.g., "Celsius", "%").
    range : Configuration for valid sensor value range.
    roc : Configuration for rate of change (RoC) checks.
    stuck : Configuration for stuck value detection.

    """

    units: str
    range: RangeConfig
    roc: RocConfig
    stuck: StuckConfig


# Overall configuration including defaults and all sensors config


@dataclass
class SensorValidationConfig:
    """Configuration for sensor validation including defaults and individual sensor settings.


    Attributes
    ----------
    defaults : Default configuration for sensor validation.
    sensors : Dictionary mapping sensor IDs to their individual configurations.
            TODO: MAKE THE SENSOR ID CORRESPOND TO THE ACTUAL SENSOR IDS IN THE SYSTEM
                --> EACH SENSOR SHOULD MATCH ITS CONFIGURATION
    """

    defaults: Defaults
    sensors: Dict[str, SensorConfig]

    @classmethod
    def from_dict(cls, data: dict) -> "SensorValidationConfig":
        defaults = Defaults(
            windows=WindowDefaults(**data["defaults"]["windows"]),
            scoring=ScoringDefaults(
                weights=ScoringWeights(**data["defaults"]["scoring"]["weights"])
            ),
        )

        sensor_map: Dict[str, SensorConfig] = {}
        for sensor_id, raw in data["sensors"].items():
            sensor_map[sensor_id] = SensorConfig(
                units=raw["units"],
                range=RangeConfig(**raw["range"]),
                roc=SensorValidationConfig._build_roc(raw.get("roc")),
                stuck=StuckConfig(**raw["stuck"]),
            )

        return cls(defaults=defaults, sensors=sensor_map)

    @staticmethod
    def _build_roc(raw: dict) -> RocConfig:
        profiles = {
            name: RocProfile(**payload) for name, payload in raw.get("profiles", {}).items()
        }
        return RocConfig(
            max_per_minute=raw.get("max_per_minute"),
            profiles=profiles,
            active_profile=raw.get("active_profile"),
        )


def load_config(path: str) -> SensorValidationConfig:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return SensorValidationConfig.from_dict(raw)


PREPROCESSING_CONFIG: SensorValidationConfig = load_config(Config.PREPROCESSING_CONFIG_PATH)
