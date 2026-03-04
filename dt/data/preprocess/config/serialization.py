from dt.communication.adapters.registry import get_adapter

from .types import (AffineCalibrationConfig, CalibrationConfig,
                    EWMASmoothingConfig, ForwardFillImputationConfig,
                    IdentityCalibrationConfig, IdentityNormalizationConfig,
                    ImputationConfig, LinearExtrapolationImputationConfig,
                    MinMaxNormalizationConfig, NormalizationConfig,
                    PassThroughSmoothingConfig,
                    PiecewiseLookupCalibrationConfig, SmoothingConfig,
                    WindowAverageImputationConfig)

_STRATEGY_MAPS: dict = {
    CalibrationConfig: {
        "identity": IdentityCalibrationConfig,
        "affine": AffineCalibrationConfig,
        "piecewise_lookup": PiecewiseLookupCalibrationConfig,
    },
    NormalizationConfig: {
        "min_max": MinMaxNormalizationConfig,
        "identity": IdentityNormalizationConfig,
    },
    ImputationConfig: {
        "forward_fill_with_decay": ForwardFillImputationConfig,
        "window_average": WindowAverageImputationConfig,
        "linear_extrapolation": LinearExtrapolationImputationConfig,
    },
    SmoothingConfig: {
        "pass_through": PassThroughSmoothingConfig,
        "ewma": EWMASmoothingConfig,
    },
}


def ensure_config_serialization():
    """
    Ensures that the serialization hooks are registered.
    This function should be called at least once before using the config classes.
    """
    adapter = get_adapter("generic")

    def _structure_strategy(base_type: type):
        mapping = _STRATEGY_MAPS[base_type]

        def hook(data: dict, _):
            if not isinstance(data, dict):
                return data
            strategy = data.get("strategy")
            if not strategy:
                raise ValueError(f"Missing 'strategy' field in {data}")
            target = mapping.get(strategy)
            if not target:
                raise ValueError(f"Unknown strategy '{strategy}'. Available: {list(mapping)}")
            return adapter.load(target, data)

        return hook

    for _base_type in _STRATEGY_MAPS:
        adapter.register_structure_hook(_base_type, _structure_strategy(_base_type))
