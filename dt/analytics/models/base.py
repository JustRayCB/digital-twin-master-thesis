"""Base protocols and contracts for analytics models."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from dt.analytics.features.base import FeatureSet
from dt.communication.dataclasses.analytics.model_metadata import ModelMetadata


@dataclass(frozen=True)
class AnalyticsInferenceResult:
    """Envelope for model inference results."""

    model_metadata: ModelMetadata
    task_key: str
    timestamp: datetime
    plant_id: str
    outputs: Dict[str, Any]
    features_used: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class OnlineModel(Protocol):
    """Protocol for models that run inference in the live system."""

    @property
    def model_metadata(self) -> ModelMetadata:
        """Structured identity for this model version."""
        ...

    @property
    def task_key(self) -> str:
        """The task this model performs (e.g., 'plant_health', 'moisture_forecast')."""
        ...

    def predict(
        self, plant_id: str, features: FeatureSet, timestamp: datetime
    ) -> AnalyticsInferenceResult:
        """Run inference on the provided features."""
        ...


class OfflineModel(Protocol):
    """Protocol for models that are trained offline and registered for tracking."""

    @property
    def model_metadata(self) -> ModelMetadata:
        """Structured identity for this model version."""
        ...

    @property
    def task_key(self) -> str:
        """The task this model performs."""
        ...

    @property
    def training_metrics(self) -> Dict[str, Any]:
        """Metrics recorded during offline training."""
        ...
