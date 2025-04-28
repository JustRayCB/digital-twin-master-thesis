from typing import Any, Dict, List, Optional

from dt.ai.models.base_model import BaseModel
from dt.ai.registry.storage import FileSystemStorage, RegistryStorage
from dt.utils.logger import get_logger


class ModelRegistry:
    """
    Model Registry for managing AI models in the Digital Twin system.

    The registry handles:
    - Model registration and versioning
    - Model storage and retrieval
    - Model deployment status
    - Model metadata and performance tracking
    """

    def __init__(self, storage: Optional[RegistryStorage] = None):
        """
        Initialize the model registry.

        Args:
            storage: Storage backend for the registry
        """
        self.storage = storage or FileSystemStorage()
        self.active_models: Dict[str, BaseModel] = {}  # Active models by name

        self.logger = get_logger(__name__)

    def register_model(self, model: BaseModel) -> bool:
        """
        Register a model in the registry.

        Args:
            model: The model to register
            topic: Optional topic where this model will be active

        Returns:
            model_id: The registered model ID
        """
        # Update the model's metadata
        model.update_metadata()

        # Register with storage
        ok = self.storage.save_model(model)
        if not ok:
            self.logger.error(f"Failed to register model {model.name}")
            return False

        self.logger.info(f"Registered model {model.name} with ID {model.model_id}")
        return True

    def load_model(self, model_name: str, version: Optional[float] = None) -> Optional[BaseModel]:
        """
        Load a model from storage by ID.

        Args:
            model_name: The model ID to load

        Returns:
            The loaded model or None if not found
        """
        # Check if model is already active
        if model_name in self.active_models:
            self.logger.info(f"Model {model_name} is already active")
            return self.active_models[model_name]

        # Load the model from storage
        model = self.storage.load_model(model_name, version)
        if not model:
            self.logger.warning(f"Model {model_name} not found")
            return None

        self.active_models[model_name] = model

        return model

    def get_model_info(
        self, model_name: str, version: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get model metadata without loading the full model.

        Args:
            model_name: Name of the model to get info for

        Returns:
            Model metadata dictionary or None if not found
        """
        return self.storage.get_model_info(model_name, version)

    def list_models(self) -> List[Dict[str, Any]]:
        """
        List all models in the registry, optionally filtered by topic.

        Returns:
            List of model metadata dictionaries
        """
        models = self.storage.list_models()

        return models

    def delete_model(self, model_name: str, version: Optional[float] = None) -> bool:
        """
        Delete a model from the registry.

        Args:
            model_name: The name of the model to delete

        Returns:
            True if successful, False otherwise
        """
        # Check if model is active for any topic
        if model_name in self.active_models:
            self.logger.warning(f"Cannot delete model {model_name} while it is active for a topic")
            return False

        # Remove from active models
        if model_name in self.active_models:
            del self.active_models[model_name]

        # Delete from storage
        success = self.storage.delete_model(model_name, version)
        if success:
            self.logger.info(f"Deleted model {model_name}")
        return success
