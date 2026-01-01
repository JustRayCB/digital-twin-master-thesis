from abc import ABC, abstractmethod

from dt.data.preprocess.config.types import (
    IdentityNormalizationConfig,
    MinMaxNormalizationConfig,
    NormalizationConfig,
)


class NormalizationStrategy(ABC):
    """Scale calibrated values into normalized ranges."""

    @abstractmethod
    def apply(self, value: float) -> float:
        """Return the normalized value for ``value``."""


class IdentityNormalization(NormalizationStrategy):
    """Return normalized values unchanged."""

    def apply(self, value: float) -> float:
        return float(value)


class MinMaxNormalization(NormalizationStrategy):
    """Scale values between configured output bounds."""

    def __init__(
        self,
        input_min: float,
        input_max: float,
        output_min: float,
        output_max: float,
        clip: bool = True,
    ) -> None:
        if input_max == input_min:
            raise ValueError("min_max requires input_max different from input_min")
        self._input_min = float(input_min)
        self._input_max = float(input_max)
        self._output_min = float(output_min)
        self._output_max = float(output_max)
        self._clip = bool(clip)

    @classmethod
    def from_parameters(cls, parameters: MinMaxNormalizationConfig) -> "MinMaxNormalization":
        return cls(
            input_min=parameters.input_min,
            input_max=parameters.input_max,
            output_min=parameters.output_min,
            output_max=parameters.output_max,
            clip=parameters.clip,
        )

    def apply(self, value: float) -> float:
        ratio = (value - self._input_min) / (self._input_max - self._input_min)
        result = self._output_min + ratio * (self._output_max - self._output_min)
        if not self._clip:
            return result
        lower = min(self._output_min, self._output_max)
        upper = max(self._output_min, self._output_max)
        if result < lower:
            return lower
        if result > upper:
            return upper
        return result


def build_normalization_strategy(params: NormalizationConfig | None) -> NormalizationStrategy:
    """Instantiate the normalization strategy described by ``params``."""
    if params is None or isinstance(params, IdentityNormalizationConfig):
        return IdentityNormalization()

    if isinstance(params, MinMaxNormalizationConfig):
        return MinMaxNormalization.from_parameters(params)

    raise ValueError(f"Unsupported normalization strategy parameters: {params}")