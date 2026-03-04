from typing import Any, TypeVar

import cattrs

from dt.communication.adapters.serializers.base import Serializer
from dt.communication.topics import Topics

T = TypeVar("T")


class GenericSerializer(Serializer[Any]):
    def __init__(self) -> None:
        self._converter = cattrs.Converter()
        self._converter.register_structure_hook(Topics, self._structure_topic)

    @staticmethod
    def _structure_topic(value, _type) -> Topics:
        if isinstance(value, Topics):
            return value
        try:
            return Topics(value)
        except ValueError:
            return Topics.from_short_name(str(value))

    def register_structure_hook(self, target_type, hook) -> None:
        self._converter.register_structure_hook(target_type, hook)

    def dump(self, obj: Any) -> Any:
        return self._converter.unstructure(obj)

    def load(self, cls: type[T], data: Any) -> T:
        return self._converter.structure(data, cls)
