from dataclasses import dataclass
from enum import StrEnum

from dt.communication.dataclasses.analytics.model_metadata import ModelMetadata


class HealthState(StrEnum):
    HEALTHY = "healthy"
    STRESSED = "stressed"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthAssessment:
    """Analytics contract for plant health state classification."""

    plant_id: int
    timestamp: float
    correlation_id: str
    state: HealthState
    score: float | None
    summary: str
    confidence: float | None = None
    model_metadata: ModelMetadata | None = None

    def __post_init__(self) -> None:
        self.plant_id = int(self.plant_id)
        self.timestamp = float(self.timestamp)
        self.correlation_id = str(self.correlation_id)
        self.state = HealthState(self.state)
        if self.score is not None:
            self.score = float(self.score)
        if self.confidence is not None:
            self.confidence = float(self.confidence)
        self.summary = str(self.summary)

        if self.model_metadata is not None and not isinstance(
            self.model_metadata, ModelMetadata
        ):
            self.model_metadata = ModelMetadata(**dict(self.model_metadata))

        if self.plant_id <= 0:
            raise ValueError("plant_id must be > 0")
        if self.timestamp <= 0:
            raise ValueError("timestamp must be > 0")
        if not self.correlation_id.strip():
            raise ValueError("correlation_id must be non-empty")
        if self.score is None and self.state is not HealthState.UNKNOWN:
            raise ValueError("score must be provided unless state is unknown")
        if self.score is not None and not 0 <= self.score <= 1:
            raise ValueError("score must be between 0 and 1")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not self.summary.strip():
            raise ValueError("summary must be non-empty")
