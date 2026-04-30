from datetime import datetime, time
from typing import Any, TypeVar

import cattrs

from dt.communication.adapters.serializers.base import Serializer
from dt.communication.topics import Topics

T = TypeVar("T")


class GenericSerializer(Serializer[Any]):
    def __init__(self) -> None:
        self._converter = cattrs.Converter()
        self._converter.register_structure_hook(Topics, self._structure_topic)
        self._converter.register_unstructure_hook(Topics, self._unstructure_topic)
        self._converter.register_structure_hook(time, self._structure_time)
        self._converter.register_unstructure_hook(time, self._unstructure_time)

    @staticmethod
    def _structure_topic(value, _type) -> Topics:
        if isinstance(value, Topics):
            return value
        try:
            return Topics(value)
        except ValueError:
            return Topics.from_short_name(str(value))

    @staticmethod
    def _unstructure_topic(value: Topics) -> str:
        return value.value

    @staticmethod
    def _structure_time(value: Any, _type: type) -> time:
        if isinstance(value, time):
            return value
        return datetime.strptime(value, "%H:%M").time()

    @staticmethod
    def _unstructure_time(value: time) -> str:
        return value.strftime("%H:%M")

    def register_structure_hook(self, target_type, hook) -> None:
        self._converter.register_structure_hook(target_type, hook)

    def dump(self, obj: Any) -> Any:
        return self._converter.unstructure(obj)

    def load(self, cls: type[T], data: Any) -> T:
        return self._converter.structure(data, cls)
