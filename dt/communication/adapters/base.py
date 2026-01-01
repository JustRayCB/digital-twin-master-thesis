from abc import ABC, abstractmethod
from typing import Any, TypeVar

from dt.utils import get_logger

T = TypeVar("T")


class SerializationAdapter(ABC):
    """Abstract class defining the interface all adapters must implement.

    Each adapter handles conversion between Python objects and a specific
    target format (dict, database row, tuple, Spark row, etc.).
    """

    def __init__(self) -> None:
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def dump(self, obj: Any) -> Any:
        """Serialize object to target format.

        Parameters
        ----------
        obj : Any
            Object to serialize (usually a dataclass instance).

        Returns
        -------
        Any
            Serialized representation in target format.
        """
        ...

    @abstractmethod
    def load(self, cls: type[T], data: Any) -> T:
        """Deserialize data from target format to object.

        Parameters
        ----------
        cls : type[T]
            Target class to deserialize into.
        data : Any
            Data in target format.

        Returns
        -------
        T
            Deserialized object instance.
        """
        ...
