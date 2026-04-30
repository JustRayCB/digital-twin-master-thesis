from dataclasses import dataclass, field

from dt.communication.dataclasses.analytics.model_metadata import ModelMetadata


@dataclass
class RecommendedAction:
    capability: str
    command: str
    duration_seconds: float | None = None

    def __post_init__(self) -> None:
        self.capability = str(self.capability)
        self.command = str(self.command)
        if self.duration_seconds is not None:
            self.duration_seconds = float(self.duration_seconds)

        if self.capability not in {"irrigation", "lighting", "fan", "heating", "advisory"}:
            raise ValueError(
                "capability must be one of: irrigation, lighting, fan, heating, advisory"
            )
        if not self.command.strip():
            raise ValueError("command must be non-empty")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("duration_seconds must be >= 0")


@dataclass
class ActionResult:
    action_index: int
    status: str

    def __post_init__(self) -> None:
        self.action_index = int(self.action_index)
        self.status = str(self.status)

        if self.action_index < 0:
            raise ValueError("action_index must be >= 0")
        if self.status not in {"accepted", "advisory_only", "rejected", "failed"}:
            raise ValueError("status must be one of: accepted, advisory_only, rejected, failed")


@dataclass
class Recommendation:
    plant_id: int
    timestamp: float
    correlation_id: str
    reason: str
    confidence: float
    actions: list[RecommendedAction] = field(default_factory=list)
    model_metadata: ModelMetadata | None = None
    action_results: list[ActionResult] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.plant_id = int(self.plant_id)
        self.timestamp = float(self.timestamp)
        self.correlation_id = str(self.correlation_id)
        self.reason = str(self.reason)
        self.confidence = float(self.confidence)

        if self.model_metadata is not None and not isinstance(self.model_metadata, ModelMetadata):
            self.model_metadata = ModelMetadata(**dict(self.model_metadata))

        self.actions = [
            action if isinstance(action, RecommendedAction) else RecommendedAction(**dict(action))
            for action in self.actions
        ]
        self.action_results = [
            result if isinstance(result, ActionResult) else ActionResult(**dict(result))
            for result in self.action_results
        ]

        if self.plant_id <= 0:
            raise ValueError("plant_id must be > 0")
        if self.timestamp <= 0:
            raise ValueError("timestamp must be > 0")
        if not self.correlation_id.strip():
            raise ValueError("correlation_id must be non-empty")
        if not self.actions:
            raise ValueError("actions must be non-empty")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not self.reason.strip():
            raise ValueError("reason must be non-empty")
