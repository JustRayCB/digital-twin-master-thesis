import json
from abc import ABC
from dataclasses import asdict, dataclass
from typing import Any, Dict, TypeVar, Union

from dt.communication.topics import Topics

T = TypeVar("T", bound="JsonSerializable")


@dataclass
class JsonSerializable(ABC):
    """
    Abstract base for message/query records:
    - consistent to_dict / to_json (with Enum-safe conversion)
    - from_dict / from_json
    - lightweight required-field validation
    """

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls: type[T], data: Dict[str, Any]) -> T:
        converted: Dict[str, Any] = {}
        for field, field_type in cls.__annotations__.items():
            if field not in data:
                raise ValueError(f"Missing field: {field}")
            value = data[field]
            if isinstance(field_type, type):
                converted[field] = field_type(value)
            else:
                converted[field] = value
        return cls(**converted)

    @classmethod
    def from_json(cls: type[T], json_data: Union[str, Dict[str, Any]]) -> T:
        data = json_data
        if isinstance(data, str):
            data = json.loads(json_data)  # type: ignore
        return cls.from_dict(data)

    @classmethod
    def validate_json(cls: type[T], json_data: Union[str, Dict[str, Any]]) -> bool:
        try:
            cls.from_json(json_data)
        except Exception:
            return False
        return True
