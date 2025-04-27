import datetime
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Dict


class ModelType(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    RULE_BASED = "rule_based"


class ModelStage(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


@dataclass
class ModelMetadata:
    """Stores metadata about a model in the registry."""

    model_id: str
    name: str = "Basic Model"
    version: str = "1.0"
    model_type: ModelType = ModelType.OFFLINE
    description: str = "A basic model for demonstration purposes."
    created_at: datetime.datetime = datetime.datetime.now()
    created_by: str = "system"
    stage: ModelStage = ModelStage.DEVELOPMENT
    metrics: Dict[str, float] = {}
    parameters: Dict[str, Any] = {}
    sensor_type: str = "basic_sensor"

    def to_dict(self) -> Dict:
        """Convert metadata to dictionary for serialization."""
        return {
            "model_id": self.model_id,
            "name": self.name,
            "version": self.version,
            "model_type": self.model_type.value,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "stage": self.stage.value,
            "metrics": self.metrics,
            "parameters": self.parameters,
            "sensor_type": self.sensor_type,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ModelMetadata":
        """Create ModelMetadata from dictionary."""
        return cls(
            model_id=data["model_id"],
            name=data["name"],
            version=data["version"],
            model_type=ModelType(data["model_type"]),
            description=data.get("description", ""),
            created_at=datetime.datetime.fromisoformat(data["created_at"]),
            created_by=data.get("created_by", "system"),
            stage=ModelStage(data["stage"]),
            metrics=data.get("metrics", {}),
            parameters=data.get("parameters", {}),
            sensor_type=data.get("sensor_type", "basic_sensor"),
        )
