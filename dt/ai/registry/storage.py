import json
import os
import pickle
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from typing_extensions import override

from dt.ai.models.base_model import BaseModel
from dt.utils.config import Config
from dt.utils.logger import get_logger


class RegistryStorage(ABC):
    """Abstract storage backend for the model registry."""

    def __init__(self):
        self.logger = get_logger(__name__)

    @abstractmethod
    def save_model(self, model: BaseModel) -> bool:
        """Save a model to storage."""
        pass

    @abstractmethod
    def load_model(self, model_name: str, version: Optional[float]) -> Optional[BaseModel]:
        """Load a model from storage."""
        pass

    @abstractmethod
    def delete_model(self, model_name: str, version: Optional[float]) -> bool:
        """Delete a model from storage."""
        pass

    @abstractmethod
    def list_models(self) -> List[Dict[str, Any]]:
        """List all models in storage."""
        pass

    @abstractmethod
    def get_model_info(self, model_name: str, version: Optional[float]) -> Optional[Dict[str, Any]]:
        """Get model metadata without loading the full model."""
        pass


class FileSystemStorage(RegistryStorage):
    """
    File system implementation of registry storage.
    Inspired from : https://ramaprashanth.com/blog/building-model-registry
    """

    def __init__(self, storage_dir: str = Config.MODELS_DIR):
        super().__init__()
        self.models_dir = storage_dir
        self.registry_file = os.path.join(self.models_dir, "registry.json")

        self.indent = 4

        # Ensure directories exist
        os.makedirs(self.models_dir, exist_ok=True)

        # Initialize active models file if it doesn't exist
        if not os.path.exists(self.registry_file):
            with open(self.registry_file, "w") as f:
                json.dump({}, f)

    def get_next_version(self, model_name: str) -> float:
        with open(self.registry_file, "r") as f:
            registry = json.load(f)

        if model_name not in registry:
            return 1
        else:
            versions = float(registry[model_name]["version"])
            return versions + 0.1

    @override
    def save_model(self, model: BaseModel) -> bool:
        """Save a model to storage."""

        try:
            version = self.get_next_version(model.name)
            model.version = version
            model_file = os.path.join(self.models_dir, f"{model.name}_{version}.pkl")
            with open(model_file, "wb") as f:
                pickle.dump(model, f)

            self._update_registry(model, version)
            self.logger.info(f"Saved model {model.name} version {version} to {model_file}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save model {model.name}: {e}")
            return False

    def _update_registry(self, model: BaseModel, new_version: float) -> None:
        """Update the registry with the new model version."""
        try:
            with open(self.registry_file, "r") as f:
                registry = json.load(f)

            if model.name not in registry:
                registry[model.name] = {}

            model_data = model.to_dict()
            model_data["version"] = new_version

            # Update the registry with the new model data
            registry[model.name][new_version] = model_data

            # Save the updated registry
            with open(self.registry_file, "w") as f:
                json.dump(registry, f, indent=4)

            self.logger.info(f"Updated registry for model {model.name}")
        except Exception as e:
            self.logger.error(f"Failed to update registry for model {model.name}: {e}")

    @override
    def load_model(self, model_name: str, version: Optional[float]) -> Optional[BaseModel]:
        """Load a model from storage."""
        with open(self.registry_file, "r") as f:
            registry = json.load(f)
        if model_name not in registry:
            self.logger.warning(f"Model {model_name} not found in registry.")
            return None
        if version is None:
            # Get the latest version
            version = max(float(v) for v in registry[model_name].keys())
        if str(version) not in registry[model_name]:
            self.logger.warning(f"Version {version} for model {model_name} not found in registry.")
            return None

        model_file = os.path.join(self.models_dir, f"{model_name}_{version}.pkl")

        try:
            with open(model_file, "rb") as f:
                model = pickle.load(f)
            self.logger.info(f"Loaded model {model_name} version {version} from {model_file}")
            return model
        except Exception as e:
            self.logger.error(f"Failed to load model {model_name} version {version}: {e}")
            return None

    @override
    def delete_model(self, model_name: str, version: Optional[float]) -> bool:
        """Delete a model from storage."""
        try:
            with open(self.registry_file, "r") as f:
                registry = json.load(f)

            if model_name not in registry:
                self.logger.warning(f"Model {model_name} not found in registry.")
                return False

            if version is None:
                # Get the latest version
                version = max(float(v) for v in registry[model_name].keys())

            if str(version) not in registry[model_name]:
                self.logger.warning(
                    f"Version {version} for model {model_name} not found in registry."
                )
                return False

            # Delete the model file
            model_file = os.path.join(self.models_dir, f"{model_name}_{version}.pkl")
            if os.path.exists(model_file):
                os.remove(model_file)
                self.logger.info(f"Deleted model file {model_file}")

            # Remove from the registry
            del registry[model_name][str(version)]

            # Save the updated registry
            with open(self.registry_file, "w") as f:
                json.dump(registry, f, indent=4)

            self.logger.info(f"Deleted model {model_name} version {version} from registry")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete model {model_name}: {e}")
            return False

    @override
    def list_models(self) -> List[Dict[str, Any]]:
        """List all models in storage."""
        models = []
        try:
            with open(self.registry_file, "r") as f:
                registry = json.load(f)

            for model_name, versions in registry.items():
                for version, model_data in versions.items():
                    models.append(
                        {
                            "model_name": model_name,
                            "version": version,
                            "description": model_data["description"],
                            "created_at": model_data["created_at"],
                            "updated_at": model_data["updated_at"],
                            "type": model_data["type"],
                        }
                    )
        except Exception as e:
            self.logger.error(f"Failed to list models: {e}")

        return models

    @override
    def get_model_info(self, model_name: str, version: Optional[float]) -> Optional[Dict[str, Any]]:
        """Get model metadata without loading the full model."""
        try:
            with open(self.registry_file, "r") as f:
                registry = json.load(f)

            if model_name not in registry:
                self.logger.warning(f"Model {model_name} not found in registry.")
                return None

            if version is None:
                # Get the latest version
                version = max(float(v) for v in registry[model_name].keys())

            if str(version) not in registry[model_name]:
                self.logger.warning(
                    f"Version {version} for model {model_name} not found in registry."
                )
                return None

            model_data = registry[model_name][str(version)]
            model_info = {
                "model_name": model_name,
                "version": version,
                "description": model_data["description"],
                "created_at": model_data["created_at"],
                "updated_at": model_data["updated_at"],
                "type": model_data["type"],
            }
            self.logger.info(f"Retrieved model info for {model_name}: {model_info}")
            return model_info

        except Exception as e:
            self.logger.error(f"Failed to get model info for {model_name}: {e}")
            return None
