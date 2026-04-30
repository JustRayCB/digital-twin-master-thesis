"""Protocol for health classification models."""

from datetime import datetime
from typing import Protocol

from dt.analytics.features.base import FeatureSet
from dt.analytics.models.base import AnalyticsInferenceResult
from dt.communication.dataclasses.analytics.model_metadata import ModelMetadata


class HealthClassifier(Protocol):
    """Protocol for models that classify plant health."""

    @property
    def model_metadata(self) -> ModelMetadata:
        """Structured identity for this model version."""
        ...

    @property
    def task_key(self) -> str:
        """The task this model performs. Should be 'plant_health'."""
        ...

    def predict(
        self, plant_id: str, features: FeatureSet, timestamp: datetime
    ) -> AnalyticsInferenceResult:
        """Evaluate features and return a health classification.

        The resulting AnalyticsInferenceResult.outputs must contain:
        - state: str (from HealthState enum string representation)
        - score: float | None (health index in [0.0, 1.0], None for unknown)
        - confidence: float | None (assessment confidence in [0.0, 1.0])
        - summary: str
        """
        ...
