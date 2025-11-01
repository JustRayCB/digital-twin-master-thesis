from dt.data.preprocess.configuration.profiles import MinMaxNormalizationParameters

from .base import NormalizationStrategy


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
    def from_parameters(cls, parameters: MinMaxNormalizationParameters) -> "MinMaxNormalization":
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
