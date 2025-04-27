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
        metrics, parameters, created_by, etc... BEFORE SAVING TO THE REGISTRY.
        """
        return self.metadata

    def to_dict(self) -> Dict[str, Any]:
        self.metadata = self.update_metadata()
        return {
            "model_id": self.model_id,
            "metadata": self.metadata.to_dict(),
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
