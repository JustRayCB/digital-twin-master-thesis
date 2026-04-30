"""Model registry for managing online and offline models."""

from typing import Dict, Optional, Tuple

from dt.analytics.models.base import OfflineModel, OnlineModel


class ModelNotFoundError(Exception):
    """Raised when a requested model is not found in the registry."""

    pass


class ModelVersionAmbiguityError(Exception):
    """Raised when a version-only lookup matches multiple models."""

    pass


class ModelRegistry:
    """Registry for managing active online models and tracking offline models."""

    def __init__(self):
        # task_key -> (model_name, version) -> OnlineModel
        self._online_models: Dict[str, Dict[Tuple[str, str], OnlineModel]] = {}
        # task_key -> active_model_key
        self._active_online_models: Dict[str, Tuple[str, str]] = {}

        # task_key -> (model_name, version) -> OfflineModel
        self._offline_models: Dict[str, Dict[Tuple[str, str], OfflineModel]] = {}

    def _model_key(self, model_name: str, version: str) -> Tuple[str, str]:
        return (model_name, version)

    def _find_model_by_version(
        self,
        models: Dict[Tuple[str, str], OnlineModel | OfflineModel],
        task_key: str,
        version: str,
    ) -> OnlineModel | OfflineModel:
        matches = [
            model
            for (model_name, model_version), model in models.items()
            if model_version == version
        ]

        if not matches:
            raise ModelNotFoundError(
                f"Model version '{version}' not found for task: {task_key}"
            )

        if len(matches) > 1:
            raise ModelVersionAmbiguityError(
                f"Model version '{version}' is ambiguous for task: {task_key}; "
                "provide a unique model name/version identity"
            )

        return matches[0]

    def register_online_model(
        self, model: OnlineModel, set_active: bool = True
    ) -> None:
        """Register an online model, optionally setting it as the active version for its task."""
        task_key = model.task_key
        model_key = self._model_key(
            model.model_metadata.model_name,
            model.model_metadata.model_version,
        )

        if task_key not in self._online_models:
            self._online_models[task_key] = {}

        self._online_models[task_key][model_key] = model

        if set_active or task_key not in self._active_online_models:
            self._active_online_models[task_key] = model_key

    def get_online_model(
        self, task_key: str, version: Optional[str] = None
    ) -> OnlineModel:
        """Retrieve an online model by task key and optional version.

        If version is not provided, returns the active version for the task.
        """
        if task_key not in self._online_models:
            raise ModelNotFoundError(
                f"No online models registered for task: {task_key}"
            )

        if version is None:
            if task_key not in self._active_online_models:
                raise ModelNotFoundError(
                    f"No active online model set for task: {task_key}"
                )
            return self._online_models[task_key][self._active_online_models[task_key]]

        return self._find_model_by_version(
            self._online_models[task_key], task_key, version
        )

    def register_offline_model(self, model: OfflineModel) -> None:
        """Register an offline model for tracking purposes."""
        task_key = model.task_key
        model_key = self._model_key(
            model.model_metadata.model_name,
            model.model_metadata.model_version,
        )

        if task_key not in self._offline_models:
            self._offline_models[task_key] = {}

        self._offline_models[task_key][model_key] = model

    def get_offline_model(self, task_key: str, version: str) -> OfflineModel:
        """Retrieve an offline model by task key and version."""
        if task_key not in self._offline_models:
            raise ModelNotFoundError(
                f"No offline models registered for task: {task_key}"
            )

        return self._find_model_by_version(
            self._offline_models[task_key], task_key, version
        )
