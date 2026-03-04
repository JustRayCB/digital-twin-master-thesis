from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Serializer(ABC, Generic[T]):
    @abstractmethod
    def dump(self, obj: T) -> Any:
        ...

    @abstractmethod
    def load(self, cls: type[T], data: Any) -> T:
        ...
