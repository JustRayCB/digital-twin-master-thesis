from dataclasses import dataclass, field
from typing import Literal, Union

# --- 1. Global System Defaults ---


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


@dataclass
class SystemDefaults:
    """Container for the default sensor validation configurations.

    Attributes
    ----------
    windows : WindowDefaults
        Default rolling window sizes for various checks.
    scoring : ScoringDefaults
        Default scoring configuration for data quality checks.
    """

    windows: WindowDefaults
    weights: ScoringWeights


# --- 2. Validation Configurations ---


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

    max_per_minute: float | None = None
    profiles: dict[str, RocProfile] = field(default_factory=dict)
    active_profile: str | None = None

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


@dataclass
class ValidationConfig:
    """Container for sensor validation configurations.
    Attributes
    ----------
    range : Optional[RangeConfig]
        Configuration for valid value range checks.
    roc : Optional[RocConfig]
        Configuration for rate of change checks.
    stuck : Optional[StuckConfig]
        Configuration for stuck value detection.
    """

    range: RangeConfig | None = None
    roc: RocConfig | None = None
    stuck: StuckConfig | None = None


# --- 3. Processing Strategies ---


# Imputation
@dataclass
class ForwardFillImputationConfig:
    """
    Configuration for forward fill with decay imputation strategy.
    This strategy fills missing sensor data by carrying forward the last
    known value, applying an exponential decay based on the time elapsed
    since the last observation.
    Attributes
    ----------
    strategy : Literal["forward_fill_with_decay"]
        The imputation strategy identifier.
    max_gap_seconds : int
        The maximum duration in seconds for which forward fill is applied. Beyond this gap, no imputation is performed.
    decay_seconds : int
        The time constant in seconds that determines the rate of exponential decay applied to the carried forward value.
    baseline : Optional[float]
        An optional baseline value to which the imputed values decay over time. If None, the values decay towards zero.
    """

    strategy: Literal["forward_fill_with_decay"] = "forward_fill_with_decay"
    max_gap_seconds: int = 300
    decay_seconds: int = 120
    baseline: float | None = None


@dataclass
class WindowAverageImputationConfig:
    """
    Configuration for windowed average imputation strategy.
    This strategy fills missing sensor data by calculating the average of
    available data points within a specified time window around the missing
    timestamp.
    Attributes
    ----------
    strategy : Literal["window_average"]
        The imputation strategy identifier.
    window_seconds : int
        The size of the time window in seconds used to compute the average for imputation.
    min_samples : int
        The minimum number of data points required within the window to perform imputation. If fewer points are available, no imputation is performed.
    max_gap_seconds : Optional[int]
        The maximum duration in seconds for which imputation is applied. Beyond this gap, no imputation is performed.
    """

    strategy: Literal["window_average"] = "window_average"
    window_seconds: int = 60
    min_samples: int = 2
    max_gap_seconds: int | None = None


@dataclass
class LinearExtrapolationImputationConfig:
    """
    Configuration for linear extrapolation imputation strategy.
    This strategy fills missing sensor data by performing linear extrapolation
    based on the nearest known data points before and after the missing timestamp.
    Attributes
    ----------
    strategy : Literal["linear_extrapolation"]
        The imputation strategy identifier.
    window_seconds : int
        The size of the time window in seconds used to identify data points for linear extrapolation.
    max_gap_seconds : Optional[int]
        The maximum duration in seconds for which imputation is applied. Beyond this gap, no imputation is performed.
    """

    strategy: Literal["linear_extrapolation"] = "linear_extrapolation"
    window_seconds: int = 60
    max_gap_seconds: int | None = None


ImputationConfig = Union[
    ForwardFillImputationConfig, WindowAverageImputationConfig, LinearExtrapolationImputationConfig
]


# Smoothing
@dataclass
class PassThroughSmoothingConfig:
    """No-op smoothing strategy that returns data unchanged."""

    strategy: Literal["pass_through"] = "pass_through"


@dataclass
class EWMASmoothingConfig:
    """
    Exponentially Weighted Moving Average (EWMA) smoothing strategy.
    This strategy smooths sensor data by applying an EWMA filter, which gives
    more weight to recent observations while exponentially decreasing the weight
    of older data points.
    Attributes
    ----------
    strategy : Literal["ewma"]
        The smoothing strategy identifier.
    alpha : float
        The smoothing factor (0 < alpha <= 1) that determines the rate of decay for older observations. A higher alpha gives more weight to recent data.
    """

    strategy: Literal["ewma"] = "ewma"
    alpha: float = 0.5


SmoothingConfig = Union[PassThroughSmoothingConfig, EWMASmoothingConfig]


# Calibration
@dataclass
class AffineCalibrationConfig:
    """
    Affine calibration strategy.
    This strategy applies a linear transformation to sensor data using a scale
    and offset.
    Attributes
    ----------
    strategy : Literal["affine"]
        The calibration strategy identifier.
    scale : float
        The scaling factor applied to the sensor data.
    offset : float
        The offset added to the scaled sensor data.
    """

    strategy: Literal["affine"] = "affine"
    scale: float = 1.0
    offset: float = 0.0


@dataclass
class IdentityCalibrationConfig:
    """Identity calibration strategy.

    This strategy leaves sensor data unchanged.
    """

    strategy: Literal["identity"] = "identity"


@dataclass
class PiecewiseSegment:
    """
    A single segment in a piecewise lookup calibration.
    This defines a mapping from an input range to a specific output value.
    Attributes
    ----------
    input_min : float
        The minimum input value for this segment.
    input_max : float
        The maximum input value for this segment.
    output : float
        The output value corresponding to the input range.
    """

    input_min: float
    input_max: float
    output: float


@dataclass
class PiecewiseLookupCalibrationConfig:
    """
    Piecewise lookup calibration strategy.
    This strategy calibrates sensor data by mapping input ranges to specific
    output values using defined segments.
    Attributes
    ----------
    strategy : Literal["piecewise_lookup"]
        The calibration strategy identifier.
    segments : Tuple[PiecewiseSegment, ...]
        A tuple of PiecewiseSegment instances defining the input-output mappings.
    """

    strategy: Literal["piecewise_lookup"] = "piecewise_lookup"
    segments: tuple[PiecewiseSegment, ...] = field(default_factory=tuple)


CalibrationConfig = Union[
    IdentityCalibrationConfig, AffineCalibrationConfig, PiecewiseLookupCalibrationConfig
]


# Normalization
@dataclass
class MinMaxNormalizationConfig:
    """
    Min-max normalization strategy.
    This strategy scales sensor data to a specified range [output_min, output_max]
    based on the defined input range [input_min, input_max]. Optionally, values can be
    clipped to the output range.
    Attributes
    ----------
    strategy : Literal["min_max"]
        The normalization strategy identifier.
    input_min : float
        The minimum input value for normalization.
    input_max : float
        The maximum input value for normalization.
    output_min : float
        The minimum output value after normalization.
    output_max : float
        The maximum output value after normalization.
    clip : bool
        Whether to clip the normalized values to the [output_min, output_max] range. If True, values outside this range are set to the nearest boundary.
    """

    strategy: Literal["min_max"] = "min_max"
    input_min: float = 0.0
    input_max: float = 1.0
    output_min: float = 0.0
    output_max: float = 1.0
    clip: bool = True


@dataclass
class IdentityNormalizationConfig:
    """
    Identity normalization strategy.
    This strategy leaves sensor data unchanged.
    Attributes
    ----------
    strategy : Literal["identity"]
        The normalization strategy identifier.
    """

    strategy: Literal["identity"] = "identity"


NormalizationConfig = Union[MinMaxNormalizationConfig, IdentityNormalizationConfig]

# --- 4. Main Sensor Configuration ---


@dataclass
class SensorConfig:
    """
    Configuration for an individual sensor.
    Attributes
    ----------
    template : Optional[str]
        The name of the template this sensor configuration extends.
    units : Optional[str]
        The measurement units of the sensor.
    validation : Optional[ValidationConfig]
        The validation configuration for the sensor.
    calibration : Optional[CalibrationConfig]
        The calibration strategy for the sensor.
    normalization : Optional[NormalizationConfig]
        The normalization strategy for the sensor.
    imputation : Optional[ImputationConfig]
        The imputation strategy for the sensor.
    smoothing : Optional[SmoothingConfig]
        The smoothing strategy for the sensor.
    """

    template: str | None = None
    units: str | None = None

    # We group validation rules
    validation: ValidationConfig | None = None

    # Strategies
    calibration: CalibrationConfig | None = None
    normalization: NormalizationConfig | None = None
    imputation: ImputationConfig | None = None
    smoothing: SmoothingConfig | None = None

    # Metadata populated by ConfigurationManager for auditability
    calibration_profile_id: str | None = None
    normalization_profile_id: str | None = None


@dataclass
class StreamConfig(SensorConfig):
    """Configuration binding for one measurement stream.

    Attributes
    ----------
    sensor : str
        Database sensor name for the physical sensor producing the stream.
    topic : str
        Topic short name for the measurement stream (for example ``temperature``).
    """

    sensor: str = ""
    topic: str = ""


# --- 5. Root Configuration ---


@dataclass
class SystemConfig:
    """Root configuration container for the data preprocessing system.
    Attributes
    ----------
    system : SystemDefaults
        Global default settings for the system.
    templates : Dict[str, SensorConfig]
        Predefined sensor configuration templates.
    streams : list[StreamConfig]
        Explicit preprocessing bindings for `(sensor, topic)` streams.
    """

    system: SystemDefaults
    templates: dict[str, SensorConfig] = field(default_factory=dict)
    streams: list[StreamConfig] = field(default_factory=list)
