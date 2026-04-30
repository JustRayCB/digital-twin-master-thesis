import json
from typing import Any, TypeVar

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.base import Serializer
from dt.communication.adapters.serializers.generic.base import \
    GenericSerializer
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag

T = TypeVar("T")
_JSON_LOAD_FALLBACK = object()


@serializes(Any, "db_row")
class DbSerializer(Serializer[T]):
    def __init__(self) -> None:
        self._generic = GenericSerializer()

    def dump(self, obj: T) -> dict[str, Any]:
        return self._generic.dump(obj)

    def load(self, cls: type[T], data: Any) -> T:
        row_dict = self._row_to_dict(data)
        return self._generic.load(cls, row_dict)

    def _to_unix(self, value: Any) -> Any:
        return value.timestamp() if value is not None else None

    def _dump_json_value(self, value: Any) -> Any:
        return json.dumps(value) if value is not None else None

    def _load_json_value(self, value: Any, *, fallback: Any = _JSON_LOAD_FALLBACK) -> Any:
        if value is None or not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value if fallback is _JSON_LOAD_FALLBACK else fallback

    def _flags_to_string(self, flags: dict[ValidationFlag, bool]) -> str:
        return "|".join(f"{flag.value}={str(value).lower()}" for flag, value in flags.items())

    def _string_to_flags(self, flags_text: str | None) -> dict[ValidationFlag, bool]:
        flags: dict[ValidationFlag, bool] = {}
        if not flags_text:
            return flags

        for flag_pair in flags_text.split("|"):
            try:
                flag_name, flag_value_str = flag_pair.split("=")
                flags[ValidationFlag(flag_name)] = flag_value_str.lower() == "true"
            except (ValueError, KeyError):
                continue

        return flags

    @staticmethod
    def _row_to_dict(data: Any) -> dict[str, Any]:
        if isinstance(data, dict):
            return data.copy()
        if hasattr(data, "_asdict"):
            return data._asdict()
        raise TypeError(f"Cannot convert {type(data)} to dict")
