from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Mapping

import yaml
from typing_extensions import override


class NormalizationParameters(ABC):
    @staticmethod
    def create(
        strategy: str,
        payload: Mapping[str, Any] | None,
        fallback: NormalizationParameters | None,
    ) -> NormalizationParameters | None:
        normalized = strategy.lower()
        if normalized == "identity":
            return None
        if normalized == "min_max":
            return MinMaxNormalizationParameters.from_dict(payload, fallback=fallback)
        raise ValueError(f"Unsupported normalization strategy '{strategy}'")

    @classmethod
    @abstractmethod
    def from_dict(
        cls, data: Mapping[str, Any], fallback: NormalizationParameters | None = None
    ) -> NormalizationParameters | None:
        raise NotImplementedError(f"{cls.__name__} must implement from_dict method")


class CalibrationParameters(ABC):
    @staticmethod
    def create(
        strategy: str,
        payload: Mapping[str, Any] | None,
        fallback: CalibrationParameters | None,
    ) -> CalibrationParameters | None:
        normalized = strategy.lower()
        if normalized == "identity":
            return None
        base: CalibrationParameters | None = None
        if normalized == "affine":
            base = fallback if isinstance(fallback, AffineCalibrationParameters) else base
            return AffineCalibrationParameters.from_dict(payload, fallback=base)
        if normalized == "piecewise_lookup":
            base = fallback if isinstance(fallback, PiecewiseLookupParameters) else base
            return PiecewiseLookupParameters.from_dict(payload, fallback=base)
        raise ValueError(f"Unsupported calibration strategy '{strategy}'")

    @classmethod
    @abstractmethod
    def from_dict(
        cls, data: Mapping[str, Any], fallback: CalibrationParameters | None = None
    ) -> CalibrationParameters | None:
        raise NotImplementedError(f"{cls.__name__} must implement from_dict method")


@dataclass
class MinMaxNormalizationParameters(NormalizationParameters):
    input_min: float
    input_max: float
    output_min: float
    output_max: float
    clip: bool = True

    @override
    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any] | None,
        fallback: NormalizationParameters | None = None,
    ) -> MinMaxNormalizationParameters:
        # NOTE: For simplicity, we assume fallback is also MinMaxNormalizationParameters if provided
        #       Since  only the same strategy would be used in fallback scenarios.
        payload = data or {}

        values: dict[str, float] = {}
        missing: list[str] = []
        for field in fields(cls):
            if field.name in payload:
                values[field.name] = float(payload[field.name])
            elif fallback is not None:
                values[field.name] = getattr(fallback, field.name)
            else:
                missing.append(field.name)
        if missing and "clip" not in missing:
            raise ValueError(f"min_max parameters missing required fields: {', '.join(missing)}")

        clip_value = values.get("clip")
        return cls(
            input_min=values["input_min"],
            input_max=values["input_max"],
            output_min=values["output_min"],
            output_max=values["output_max"],
            clip=bool(clip_value) if clip_value is not None else True,
        )


@dataclass
class AffineCalibrationParameters(CalibrationParameters):
    scale: float = 1.0
    offset: float = 0.0

    @override
    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any] | None,
        fallback: AffineCalibrationParameters | None = None,
    ) -> AffineCalibrationParameters:
        payload = data or {}
        base = fallback or cls()
        scale = float(payload.get("scale", base.scale))
        offset = float(payload.get("offset", base.offset))
        return cls(scale=scale, offset=offset)


@dataclass
class PiecewiseSegment:
    input_min: float
    input_max: float
    output: float

    def __post_init__(self) -> None:
        if self.input_max <= self.input_min:
            raise ValueError("piecewise segment requires input_max greater than input_min")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PiecewiseSegment:
        missing = [field.name for field in fields(cls) if field.name not in data]
        if missing:
            raise ValueError(f"piecewise segment missing required fields: {', '.join(missing)}")
        return cls(
            input_min=float(data["input_min"]),
            input_max=float(data["input_max"]),
            output=float(data["output"]),
        )


@dataclass
class PiecewiseLookupParameters(CalibrationParameters):
    segments: tuple[PiecewiseSegment, ...]

    @override
    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any] | None,
        fallback: PiecewiseLookupParameters | None = None,
    ) -> PiecewiseLookupParameters:
        if not data or "segments" not in data:
            if fallback is None:
                raise ValueError("piecewise_lookup parameters require 'segments'")
            return fallback

        segments_raw = data["segments"]
        if not isinstance(segments_raw, list) or not segments_raw:
            raise ValueError("piecewise_lookup requires non-empty 'segments' list")
        segments = tuple(PiecewiseSegment.from_dict(entry) for entry in segments_raw)
        return cls(segments=segments)


ProfileParameters = CalibrationParameters | NormalizationParameters | None


@dataclass
class ProfileDefinition:
    """Concrete strategy configuration for calibration or normalization."""

    profile_id: str
    strategy: str
    parameters: ProfileParameters

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        section: str,
        context: str,
        fallback: ProfileDefinition | None = None,
    ) -> ProfileDefinition:
        profile_id = data.get("profile_id") or (fallback.profile_id if fallback else None)
        if profile_id is None:
            raise ValueError(f"{section} {context} is missing 'profile_id'")

        strategy = data.get("strategy") or (fallback.strategy if fallback else None)
        if strategy is None:
            raise ValueError(f"{section} {context} is missing 'strategy'")

        raw_parameters = data.get("parameters")
        payload = raw_parameters if isinstance(raw_parameters, Mapping) else None

        if section == "calibration":
            parameters = CalibrationParameters.create(
                strategy=strategy,
                payload=payload,
                fallback=(
                    fallback.parameters
                    if fallback is not None
                    and isinstance(fallback.parameters, CalibrationParameters)
                    else None
                ),
            )
        elif section == "normalization":
            parameters = NormalizationParameters.create(
                strategy=strategy,
                payload=payload,
                fallback=(
                    fallback.parameters
                    if fallback is not None
                    and isinstance(fallback.parameters, NormalizationParameters)
                    else None
                ),
            )
        else:
            raise ValueError(f"Unsupported section '{section}'")

        return cls(profile_id=profile_id, strategy=strategy, parameters=parameters)


@dataclass
class SensorProfileAssignment:
    """Profile bound to a specific sensor identifier."""

    sensor_type: str
    profile: ProfileDefinition

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        section: str,
        context: str,
        fallback: ProfileDefinition,
    ) -> SensorProfileAssignment:
        sensor_type = data.get("sensor_type")
        if sensor_type is None:
            raise ValueError(f"{section} {context} is missing required field 'sensor_type'")

        profile = ProfileDefinition.from_dict(
            data,
            section=section,
            context=context,
            fallback=fallback,
        )
        return cls(sensor_type=sensor_type, profile=profile)


@dataclass
class ProfileCollection:
    """Profile definitions grouped by sensor type and per-sensor overrides."""

    defaults: dict[str, ProfileDefinition]
    overrides: dict[str, SensorProfileAssignment]

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        section: str,
    ) -> ProfileCollection:
        defaults_raw = data.get("defaults") or {}
        overrides_raw = data.get("overrides") or {}

        # Default sensors models/types configurations profiles
        defaults: dict[str, ProfileDefinition] = {}
        for sensor_type, payload in defaults_raw.items():
            defaults[sensor_type] = ProfileDefinition.from_dict(
                payload,
                section=section,
                context=f"default for '{sensor_type}'",
            )

        # Per-sensor overrides
        overrides: dict[str, SensorProfileAssignment] = {}
        for sensor_id, payload in overrides_raw.items():
            sensor_type = payload.get("sensor_type")
            if sensor_type is None:
                raise ValueError(
                    f"{section} override '{sensor_id}' is missing required field 'sensor_type'"
                )
            fallback_profile = defaults.get(sensor_type)
            if fallback_profile is None:
                raise KeyError(
                    f"{section} override '{sensor_id}' references unknown sensor type '{sensor_type}'"
                )
            overrides[sensor_id] = SensorProfileAssignment.from_dict(
                payload,
                section=section,
                context=f"override '{sensor_id}'",
                fallback=fallback_profile,
            )

        return cls(defaults=defaults, overrides=overrides)


@dataclass
class ProfileConfiguration:
    """Bundle of calibration and normalization profile collections."""

    calibration: ProfileCollection
    normalization: ProfileCollection

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ProfileConfiguration:
        calibration = ProfileCollection.from_dict(
            data.get("calibration_profiles", {}),
            section="calibration",
        )
        normalization = ProfileCollection.from_dict(
            data.get("normalization_profiles", {}),
            section="normalization",
        )
        return cls(calibration=calibration, normalization=normalization)

    @classmethod
    def load(cls, path: str | Path) -> ProfileConfiguration:
        with Path(path).expanduser().open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, Mapping):
            raise ValueError("Profile configuration root must be a mapping")
        return cls.from_dict(data)


def load_profile_configuration(path: str | Path) -> ProfileConfiguration:
    """Convenience wrapper mirroring the original loader API."""
    return ProfileConfiguration.load(path)
