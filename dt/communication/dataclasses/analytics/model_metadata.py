from dataclasses import dataclass


@dataclass
class ModelMetadata:
    """Minimal analytics model identity contract."""

    model_name: str
    model_version: str

    def __post_init__(self) -> None:
        self.model_name = str(self.model_name)
        self.model_version = str(self.model_version)

        if not self.model_name.strip():
            raise ValueError("model_name must be non-empty")
        if not self.model_version.strip():
            raise ValueError("model_version must be non-empty")
