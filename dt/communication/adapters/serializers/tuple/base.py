from typing import Any, TypeVar

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.base import Serializer
from dt.communication.adapters.serializers.generic.base import \
    GenericSerializer

T = TypeVar("T")


@serializes(Any, "tuple")
class TupleSerializer(Serializer[Any]):
    def __init__(self) -> None:
        self._generic = GenericSerializer()

    def dump(self, obj: Any) -> tuple:
        data = self._generic.dump(obj)
        return tuple(data.values())

    def load(self, cls: type[T], data: tuple) -> T:
        if not data:
            raise (TypeError(f"TupleAdapter cannot load {cls.__name__} from None or empty data"))
        return cls(*data)
