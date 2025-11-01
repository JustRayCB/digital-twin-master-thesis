from dt.data.preprocess.configuration.profiles import (
    MinMaxNormalizationParameters,
    ProfileDefinition,
)

from .base import NormalizationStrategy
from .identity import IdentityNormalization
from .min_max import MinMaxNormalization


def build_normalization_strategy(profile: ProfileDefinition) -> NormalizationStrategy:
    """Instantiate the normalization strategy described by ``profile``."""
    strategy = profile.strategy.lower()
    parameters = profile.parameters

    if strategy == "identity":
        return IdentityNormalization()
    if strategy == "min_max":
        if not isinstance(parameters, MinMaxNormalizationParameters):
            raise TypeError("Min-max normalization requires MinMaxNormalizationParameters")
        return MinMaxNormalization.from_parameters(parameters)

    raise ValueError(f"Unsupported normalization strategy '{profile.strategy}'")
