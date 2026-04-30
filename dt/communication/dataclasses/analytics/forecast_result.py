from dataclasses import dataclass
from typing import Any

from dt.communication.dataclasses.analytics.model_metadata import ModelMetadata


@dataclass
class ForecastResult:
    """Analytics contract for forecast outputs."""

    plant_id: int
    timestamp: float
    correlation_id: str
    metric: str
    horizon_seconds: int
    predicted_value: float
    unit: str
    model_metadata: ModelMetadata | None = None
    features_used: list[str] | None = None
    inference_metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.plant_id = int(self.plant_id)
        self.timestamp = float(self.timestamp)
        self.correlation_id = str(self.correlation_id)
        self.metric = str(self.metric)
        self.horizon_seconds = int(self.horizon_seconds)
        self.predicted_value = float(self.predicted_value)
        self.unit = str(self.unit)
        if self.model_metadata is not None and not isinstance(
            self.model_metadata, ModelMetadata
        ):
            self.model_metadata = ModelMetadata(**dict(self.model_metadata))
        if self.features_used is not None:
            self.features_used = [
                str(feature_name) for feature_name in self.features_used
            ]
        if self.inference_metadata is not None:
            self.inference_metadata = dict(self.inference_metadata)

        if self.plant_id <= 0:
            raise ValueError("plant_id must be > 0")
        if self.timestamp <= 0:
            raise ValueError("timestamp must be > 0")
        if not self.correlation_id.strip():
            raise ValueError("correlation_id must be non-empty")
        if not self.metric.strip():
            raise ValueError("metric must be non-empty")
        if self.horizon_seconds <= 0:
            raise ValueError("horizon_seconds must be > 0")
        if not self.unit.strip():
            raise ValueError("unit must be non-empty")
