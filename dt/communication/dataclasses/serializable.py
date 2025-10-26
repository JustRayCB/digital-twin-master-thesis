import json
from abc import ABC
from dataclasses import asdict, dataclass, fields
from typing import Any, TypeVar


T = TypeVar("T", bound="JsonSerializable")


@dataclass
class JsonSerializable(ABC):
    """Abstract base class for serializable message and query records.

    This class provides a consistent interface for converting dataclass instances
    to and from dictionary and JSON formats. It also includes lightweight
    validation to ensure that all required fields are present during
    deserialization.
    """

    def to_dict(self) -> dict[str, Any]:
        """Convert the dataclass instance to a dictionary.

        Returns
        -------
        Dict[str, Any]
            A dictionary representation of the dataclass instance.
        """
        d = asdict(self)
        return d

    def to_json(self) -> str:
        """Convert the dataclass instance to a JSON string.

        Returns
        -------
        str
            A JSON string representation of the dataclass instance.
        """
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Create a dataclass instance from a dictionary.

        This method performs basic validation to ensure all required fields
        are present in the input dictionary.

        Parameters
        ----------
        data : Dict[str, Any]
            The dictionary from which to create the dataclass instance.

        Returns
        -------
        T
            An instance of the dataclass.

        Raises
        ------
        ValueError
            If a required field is missing from the input dictionary.
        """
        converted: dict[str, Any] = {}
        for field in fields(cls):
            name = field.name
            if name not in data:
                raise ValueError(f"Missing field: {name}")
            value = data[name]
            field_type = field.type
            if isinstance(field_type, type):
                converted[name] = field_type(value)
            else:
                converted[name] = value
        return cls(**converted)

    @classmethod
    def from_json(cls: type[T], json_data: str | dict[str, Any]) -> T:
        """Create a dataclass instance from a JSON string or dictionary.

        Parameters
        ----------
        json_data : Union[str, Dict[str, Any]]
            The JSON string or dictionary from which to create the instance.

        Returns
        -------
        T
            An instance of the dataclass.
        """
        data = json_data
        if isinstance(data, str):
            data = json.loads(json_data)  # type: ignore
        return cls.from_dict(data)

    @classmethod
    def validate_json(cls: type[T], json_data: str | dict[str, Any]) -> bool:
        """Validate a JSON string or dictionary against the dataclass schema.

        Parameters
        ----------
        json_data : Union[str, Dict[str, Any]]
            The JSON string or dictionary to validate.

        Returns
        -------
        bool
            ``True`` if the JSON is valid, ``False`` otherwise.
        """
        try:
            cls.from_json(json_data)
        except Exception:
            return False
        return True
