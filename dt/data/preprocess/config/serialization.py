from typing import Any

from dt.communication.adapters.generic import GenericAdapter
from dt.communication.adapters.registry import get_adapter
from dt.utils import get_logger

from .types import (
    AffineCalibrationConfig,
    CalibrationConfig,
    EWMASmoothingConfig,
    ForwardFillImputationConfig,
    IdentityCalibrationConfig,
    IdentityNormalizationConfig,
    ImputationConfig,
    LinearExtrapolationImputationConfig,
    MinMaxNormalizationConfig,
    NormalizationConfig,
    PassThroughSmoothingConfig,
    PiecewiseLookupCalibrationConfig,
    SmoothingConfig,
    WindowAverageImputationConfig,
)

logger = get_logger(__name__)

_CONFIGURED = False


def ensure_config_serialization() -> None:
    """Register structure hooks needed to load preprocessing configuration types."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    adapter = get_adapter("generic")
    if not isinstance(adapter, GenericAdapter):
        logger.warning(
            "Generic adapter is not available; preprocessing config hooks not registered."
        )
        _CONFIGURED = True
        return

    def structure_strategy(data: Any, type_mapping: dict[str, type]) -> Any:
        if not isinstance(data, dict):
            return data

        strategy = data.get("strategy")
        if not strategy:
            raise ValueError(f"Missing 'strategy' field in {data}")

        target_type = type_mapping.get(strategy)
        if not target_type:
            raise ValueError(
                f"Unknown strategy '{strategy}'. Available: {list(type_mapping.keys())}"
            )

        return adapter.load(target_type, data)

    adapter.register_structure_hook(
        CalibrationConfig,
        lambda d, _: structure_strategy(
            d,
            {
                "identity": IdentityCalibrationConfig,
                "affine": AffineCalibrationConfig,
                "piecewise_lookup": PiecewiseLookupCalibrationConfig,
            },
        ),
    )

    adapter.register_structure_hook(
        NormalizationConfig,
        lambda d, _: structure_strategy(
            d,
            {
                "min_max": MinMaxNormalizationConfig,
                "identity": IdentityNormalizationConfig,
            },
        ),
    )

    adapter.register_structure_hook(
        ImputationConfig,
        lambda d, _: structure_strategy(
            d,
            {
                "forward_fill_with_decay": ForwardFillImputationConfig,
                "window_average": WindowAverageImputationConfig,
                "linear_extrapolation": LinearExtrapolationImputationConfig,
            },
        ),
    )

    adapter.register_structure_hook(
        SmoothingConfig,
        lambda d, _: structure_strategy(
            d,
            {
                "pass_through": PassThroughSmoothingConfig,
                "ewma": EWMASmoothingConfig,
            },
        ),
    )

    _CONFIGURED = True
