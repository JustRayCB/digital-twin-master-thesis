from dt.data.preprocess.configuration.profiles import (
    AffineCalibrationParameters,
    PiecewiseLookupParameters,
    ProfileDefinition,
)

from .affine import AffineCalibration
from .base import CalibrationStrategy
from .identity import IdentityCalibration
from .piecewise import PiecewiseLookupCalibration


def build_calibration_strategy(profile: ProfileDefinition) -> CalibrationStrategy:
    """Instantiate the calibration strategy described by ``profile``."""
    strategy = profile.strategy.lower()
    parameters = profile.parameters

    if strategy == "identity":
        return IdentityCalibration()
    if strategy == "affine":
        if not isinstance(parameters, AffineCalibrationParameters):
            raise TypeError("Affine calibration requires AffineCalibrationParameters")
        return AffineCalibration.from_parameters(parameters)
    if strategy == "piecewise_lookup":
        if not isinstance(parameters, PiecewiseLookupParameters):
            raise TypeError("Piecewise lookup calibration requires PiecewiseLookupParameters")
        return PiecewiseLookupCalibration.from_parameters(parameters)

    raise ValueError(f"Unsupported calibration strategy '{profile.strategy}'")
