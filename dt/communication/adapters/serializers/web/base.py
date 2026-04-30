from __future__ import annotations

from typing import Any, TypeVar

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.base import Serializer
from dt.communication.adapters.serializers.generic.base import GenericSerializer

T = TypeVar("T")


@serializes(Any, "web")
class WebSerializer(Serializer[T]):
    def __init__(self) -> None:
        self._generic = GenericSerializer()

    @staticmethod
    def seconds_to_browser_time(value: float | int | None) -> int | None:
        if value is None:
            return None
        return int(float(value) * 1000)

    @staticmethod
    def browser_time_to_seconds(value: float | int | None) -> float | None:
        if value is None:
            return None
        return float(value) / 1000.0

    def convert_timestamp_field(self, payload: dict[str, Any], field: str) -> dict[str, Any]:
        if field not in payload:
            return payload

        payload["time"] = self.seconds_to_browser_time(payload.pop(field))
        return payload

    def move_timestamp_to_time(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.convert_timestamp_field(payload, "timestamp")

    def dump(self, obj: T) -> Any:
        generic_dump: Any = self._generic.dump(obj)
        if not isinstance(generic_dump, dict):
            return generic_dump

        payload: dict[str, Any] = generic_dump
        return self.move_timestamp_to_time(payload)

    def load(self, cls: type[T], data: Any) -> T:
        return self._generic.load(cls, data)
