from dataclasses import dataclass
from typing import Union
from collections.abc import Mapping

import yaml


@dataclass
class WindowDefaults:
    """Defines default rolling window sizes for data quality checks.

    Attributes
    ----------
    small_sec : int
        Small window size in seconds for quick checks.
    medium_sec : int
        Medium window size in seconds for standard checks, such as rate of change.
    big_sec : int
        Large window size in seconds for long-term checks, such as stuck value detection.
    """

    small_sec: int
    medium_sec: int
    big_sec: int


@dataclass
class ScoringWeights:
    """Defines default weights for data quality scoring.

    Data quality checks include range, rate of change, and stuck value
    detection. Each weight represents the importance of the corresponding check
    in the overall score. Increasing a weight increases the influence of that
    check on the final score.

    Attributes
    ----------
    range_ok : float
        Weight for the range check.
    roc_ok : float
        Weight for the rate of change (RoC) check.
    stuck_ok : float
        Weight for the stuck value check.
    """

    range_ok: float
    roc_ok: float
    stuck_ok: float

    def to_dict(self) -> dict:
        """Convert the ScoringWeights instance to a dictionary.

        Returns
        -------
        dict
            A dictionary representation of the ScoringWeights instance.
        """
        return {
            "range_ok": self.range_ok,
            "roc_ok": self.roc_ok,
            "stuck_ok": self.stuck_ok,
        }


@dataclass
class ScoringDefaults:
    """Defines the default scoring configuration for data quality checks.

    This class could be extended in the future to include other parameters
    such as thresholds.

    Attributes
    ----------
    weights : ScoringWeights
        The weights for the different data quality checks.
    """

    weights: ScoringWeights


@dataclass
class Defaults:
    """Container for the default sensor validation configurations.

    Attributes
    ----------
    windows : WindowDefaults
        Default rolling window sizes for various checks.
    scoring : ScoringDefaults
        Default scoring configuration for data quality checks.
    """

    windows: WindowDefaults
    scoring: ScoringDefaults


# INDIVIDUAL SENSORS CONFIGURATION


@dataclass
class RangeConfig:
    """Configuration for a sensor's valid value range.

    Attributes
    ----------
    min : float
        The minimum valid value for the sensor reading.
    max : float
        The maximum valid value for the sensor reading.
    """

    min: float
    max: float


@dataclass
class RocProfile:
    """Configuration for a single rate of change (RoC) profile.

    This defines the maximum allowed rate of change for a sensor value within
    a one-minute interval for a specific scenario (e.g., "indoor").

    Attributes
    ----------
    max_per_minute : float
        The maximum allowed rate of change per minute.
    """

    max_per_minute: float


@dataclass
class RocConfig:
    """Configuration for rate of change (RoC) checks.

    This includes multiple profiles for different scenarios (e.g., "indoor",
    "outdoor") and an optional active profile. If no active profile is set,
    the `max_per_minute` attribute is used as a default limit.

    Attributes
    ----------
    max_per_minute : Optional[float]
        Default maximum allowed rate of change per minute if no profile is
        active.
    profiles : Dict[str, RocProfile]
        A dictionary of named RoC profiles.
    active_profile : Optional[str]
        The name of the currently active RoC profile. If ``None``,
        `max_per_minute` is used.
    """

    max_per_minute: float | None
    profiles: dict[str, RocProfile]
    active_profile: str | None

    @property
    def active_max_per_minute(self) -> float | None:
        """Get the max rate of change for the active profile.

        If no active profile is set, this returns the default `max_per_minute`.

        Returns
        -------
        Optional[float]
            The maximum allowed rate of change per minute for the active
            profile, or the default value if no profile is active.
        """
        if self.active_profile and self.active_profile in self.profiles:
            return self.profiles[self.active_profile].max_per_minute
        return self.max_per_minute

    def set_active_profile(self, profile_name: str) -> None:
        """Activate the specified ROC profile for validations.

        Parameters
        ----------
        profile_name : str
            Identifier of the profile to activate.

        Raises
        ------
        KeyError
            If profile_name is not present in self.profiles.
        ValueError
            If the selected profile omits max_per_minute.
        """
        if profile_name not in self.profiles:
            raise KeyError(profile_name)

        profile = self.profiles[profile_name]
        if profile.max_per_minute is None:
            raise ValueError(f"ROC profile '{profile_name}' missing max_per_minute limit")

        self.active_profile = profile_name


@dataclass
class StuckConfig:
    """Configuration for stuck value detection.

    This defines the maximum duration a sensor value can remain unchanged
    before being flagged as stuck.

    Attributes
    ----------
    max_flat_seconds : int
        The maximum duration in seconds that a sensor value can remain
        unchanged.
    """

    max_flat_seconds: int


DEFAULT_IMPUTATION_MAX_GAP = 300
DEFAULT_IMPUTATION_DECAY_SECONDS = 120
DEFAULT_IMPUTATION_WINDOW_SECONDS = 60
DEFAULT_IMPUTATION_MIN_SAMPLES = 2


@dataclass
class ForwardFillImputationConfig:
    """Configuration for forward-fill with decay imputation."""

    max_gap_seconds: int = DEFAULT_IMPUTATION_MAX_GAP
    decay_seconds: int = DEFAULT_IMPUTATION_DECAY_SECONDS
    baseline: float | None = None
    strategy: str = "forward_fill_with_decay"


@dataclass
class WindowAverageImputationConfig:
    """Configuration for windowed average imputation."""

    window_seconds: int = DEFAULT_IMPUTATION_WINDOW_SECONDS
    min_samples: int = DEFAULT_IMPUTATION_MIN_SAMPLES
    max_gap_seconds: int | None = None
    strategy: str = "window_average"


@dataclass
class LinearExtrapolationImputationConfig:
    """Configuration for linear extrapolation imputation."""

    window_seconds: int = DEFAULT_IMPUTATION_WINDOW_SECONDS
    max_gap_seconds: int | None = None
    strategy: str = "linear_extrapolation"


ImputationConfig = Union[
    ForwardFillImputationConfig,
    WindowAverageImputationConfig,
    LinearExtrapolationImputationConfig,
]


@dataclass
class PassThroughSmoothingConfig:
    """Configuration for pass-through smoothing (no-op)."""

    strategy: str = "pass_through"


@dataclass
class EWMASmoothingConfig:
    """Configuration for exponentially weighted moving average smoothing."""

    alpha: float = 0.5
    strategy: str = "ewma"


SmoothingConfig = Union[PassThroughSmoothingConfig, EWMASmoothingConfig]


@dataclass
class SensorConfig:
    """Configuration for an individual sensor's validation parameters.

    Attributes
    ----------
    units : str
        The units of measurement for the sensor (e.g., "Celsius", "%").
    range : RangeConfig
        Configuration for the valid sensor value range.
    roc : RocConfig
        Configuration for rate of change (RoC) checks.
    stuck : StuckConfig
        Configuration for stuck value detection.
    imputation : Optional[ImputationConfig]
        Configuration for the imputation strategy, if defined.
    """

    units: str
    range: RangeConfig
    roc: RocConfig
    stuck: StuckConfig
    imputation: ImputationConfig | None = None
    smoothing: SmoothingConfig | None = None


# Overall configuration including defaults and all sensors config


@dataclass
class SensorValidationConfig:
    """Main configuration for sensor validation.

    This class includes both default settings and configurations for
    individual sensors.

    Attributes
    ----------
    defaults : Defaults
        The default configuration for sensor validation.
    sensors : Dict[str, SensorConfig]
        A dictionary mapping sensor IDs to their individual configurations.
            TODO: MAKE THE SENSOR ID CORRESPOND TO THE ACTUAL SENSOR IDS IN THE SYSTEM
                --> EACH SENSOR SHOULD MATCH ITS CONFIGURATION
    """

    defaults: Defaults
    sensors: dict[str, SensorConfig]

    @classmethod
    def load(cls, path: str) -> "SensorValidationConfig":
        """Load the sensor validation configuration from a YAML file.

        Parameters
        ----------
        path : str
            The path to the YAML configuration file.

        Returns
        -------
        SensorValidationConfig
            An instance of the SensorValidationConfig class.
        """
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, data: dict) -> "SensorValidationConfig":
        """Load the sensor validation configuration from a dictionary.

        Parameters
        ----------
        data : dict
            The dictionary containing the configuration data, typically loaded
            from a YAML file.

        Returns
        -------
        SensorValidationConfig
            An instance of the SensorValidationConfig class.
        """
        defaults = Defaults(
            windows=WindowDefaults(**data["defaults"]["windows"]),
            scoring=ScoringDefaults(
                weights=ScoringWeights(**data["defaults"]["scoring"]["weights"])
            ),
        )

        sensor_map: dict[str, SensorConfig] = {}
        for sensor_id, raw in data["sensors"].items():
            sensor_map[sensor_id] = SensorConfig(
                units=raw["units"],
                range=RangeConfig(**raw["range"]),
                roc=SensorValidationConfig._build_roc(raw.get("roc")),
                stuck=StuckConfig(**raw["stuck"]),
                imputation=SensorValidationConfig._build_imputation(raw.get("imputation")),
                smoothing=SensorValidationConfig._build_smoothing(raw.get("smoothing")),
            )

        return cls(defaults=defaults, sensors=sensor_map)

    @staticmethod
    def _build_roc(raw: dict) -> RocConfig:
        """Build a RocConfig object from a raw dictionary.

        Parameters
        ----------
        raw : dict
            The dictionary containing the RoC configuration.

        Returns
        -------
        RocConfig
            An instance of the RocConfig class.
        """
        profiles = {
            name: RocProfile(**payload) for name, payload in raw.get("profiles", {}).items()
        }
        return RocConfig(
            max_per_minute=raw.get("max_per_minute"),
            profiles=profiles,
            active_profile=raw.get("active_profile"),
        )

    def apply_roc_overrides(self, overrides: Mapping[str, str]) -> None:
        """Apply rate of change (RoC) profile overrides to specific sensors.

        Parameters
        ----------
        overrides : Mapping[str, str]
            Mapping of sensor IDs to the desired active RoC profile names.
            e.g., {"sensor_id": "profile_name"}

        Raises
        ------
        KeyError
            If an override references a sensor ID absent from self.sensors.
        ValueError
            If a targeted sensor lacks RoC profile definitions.
        """

        for sensor_id, profile_name in overrides.items():
            sensor = self.sensors[sensor_id]
            if not sensor.roc.profiles:
                raise ValueError(f"Sensor '{sensor_id}' does not define ROC profiles.")

            sensor.roc.set_active_profile(profile_name)

    @staticmethod
    def _build_imputation(raw: dict | None) -> ImputationConfig | None:
        """Build imputation configuration from the raw dictionary."""
        if not raw:
            return None
        strategy = raw.get("strategy", "forward_fill_with_decay")
        if strategy == "forward_fill_with_decay":
            baseline_raw = raw.get("baseline")
            baseline = float(baseline_raw) if baseline_raw is not None else None
            return ForwardFillImputationConfig(
                max_gap_seconds=int(raw.get("max_gap_seconds", DEFAULT_IMPUTATION_MAX_GAP)),
                decay_seconds=int(raw.get("decay_seconds", DEFAULT_IMPUTATION_DECAY_SECONDS)),
                baseline=baseline,
            )
        if strategy == "window_average":
            max_gap = raw.get("max_gap_seconds")
            return WindowAverageImputationConfig(
                window_seconds=int(raw.get("window_seconds", DEFAULT_IMPUTATION_WINDOW_SECONDS)),
                min_samples=int(raw.get("min_samples", DEFAULT_IMPUTATION_MIN_SAMPLES)),
                max_gap_seconds=int(max_gap) if max_gap is not None else None,
            )
        if strategy == "linear_extrapolation":
            max_gap = raw.get("max_gap_seconds")
            return LinearExtrapolationImputationConfig(
                window_seconds=int(raw.get("window_seconds", DEFAULT_IMPUTATION_WINDOW_SECONDS)),
                max_gap_seconds=int(max_gap) if max_gap is not None else None,
            )
        raise ValueError(f"Unsupported imputation strategy '{strategy}'")

    @staticmethod
    def _build_smoothing(raw: dict | None) -> SmoothingConfig | None:
        """Build smoothing configuration from the raw dictionary."""
        if not raw:
            return None
        strategy = raw.get("strategy", "pass_through")
        if strategy == "pass_through":
            return PassThroughSmoothingConfig()
        if strategy == "ewma":
            alpha = float(raw.get("alpha", 0.5))
            return EWMASmoothingConfig(alpha=alpha)
        raise ValueError(f"Unsupported smoothing strategy '{strategy}'")
