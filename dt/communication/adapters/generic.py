"""Generic adapter for Python native type conversions.

Uses cattrs to convert dataclasses to/from Python native types (dict, list, str, etc.).
This format is suitable for JSON serialization, Kafka messages, and REST APIs.
"""

from typing import Any, TypeVar

import cattrs
from typing_extensions import override

from .base import SerializationAdapter

T = TypeVar("T")


class GenericAdapter(SerializationAdapter):
    """Adapter for converting objects to/from Python native types.

    Uses cattrs for automatic structure/unstructure with custom hooks for:
    - New alert DTOs (AlertDefinition, AlertHistoryEvent, SensorAlertEvent, ExternalAlertEvent) use default cattrs behavior
    """

    def __init__(self) -> None:
        """Initialize the adapter with cattrs converter and hooks."""
        self._converter = cattrs.Converter()

    def register_structure_hook(self, target_type, hook) -> None:
        """Register a custom structure hook on the underlying converter."""
        self._converter.register_structure_hook(target_type, hook)

    @override
    def dump(self, obj: Any) -> Any:
        """Serialize object to Python native types.

        Converts dataclasses to dicts with:
        - Enums → strings
        - dict[Enum, ...] → dict[str, ...]
        - Nested dataclasses → nested dicts

        Parameters
        ----------
        obj : Any
            Object to serialize (typically a dataclass).

        Returns
        -------
        Any
            Python native representation (dict, list, str, int, float, bool, None).
        """
        return self._converter.unstructure(obj)

    @override
    def load(self, cls: type[T], data: Any) -> T:
        """Deserialize data from Python native types.

        Converts dicts to dataclasses with:
        - Strings → enums
        - dict[str, ...] → dict[Enum, ...]
        - Type coercion via __post_init__

        Parameters
        ----------
        cls : type[T]
            Target class to deserialize into.
        data : Any
            Data in Python native format (typically dict).

        Returns
        -------
        T
            Deserialized object instance.
        """
        return self._converter.structure(data, cls)
