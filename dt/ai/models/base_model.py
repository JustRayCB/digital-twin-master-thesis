"""Abstract base class for all predictive models in the digital twin system."""

import datetime
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from dt.ai.registry import ModelMetadata


class BaseModel(ABC):
    """Base class for all models in the Digital Twin system."""

    def __init__(
        self,
        model_id: Optional[str],
        metadata: Optional[ModelMetadata] = None,
    ):
        self.model_id: str = model_id if model_id else str(uuid.uuid4())
        self.metadata = (
            metadata if metadata else ModelMetadata(model_id=model_id)  # pyright: ignore[]
        )

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def created_at(self) -> datetime.datetime:
        return self.metadata.created_at

    @property
    def updated_at(self) -> datetime.datetime:
        return self.metadata.updated_at

    @property
    def version(self) -> str:
        return self.metadata.version

    @version.setter
    def version(self, version: float) -> None:
        self.metadata.version = str(version)

    @abstractmethod
    def predict(self, inputs: Dict[str, Any]) -> Any:
        pass

    def get_metadata(self) -> Dict[str, Any]:
        return self.metadata.to_dict()

    @abstractmethod
    def update_metadata(self) -> ModelMetadata:
        """
        Convert model to metadata.

        Returns:
            ModelMetadata object
        """
        """
        Each subclass should implement this method to update mandatory fields like 
        updated_at, metrics, parameters, created_by, etc... BEFORE SAVING TO THE REGISTRY.
        """
        return self.metadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            **self.metadata.to_dict(),  # Include metadata fields in root dict
            "type": self.__class__.__name__,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseModel":
        """
        Create model from dictionary.

        Args:
            data: Dictionary representation of model

        Returns:
            Instantiated model
        """
        # This must be implemented by subclasses
        raise NotImplementedError("Subclasses must implement from_dict")
