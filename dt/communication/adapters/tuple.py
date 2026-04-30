from dataclasses import asdict, astuple
from typing import Any, TypeVar

from typing_extensions import override

from dt.communication.adapters.base import SerializationAdapter
from dt.communication.dataclasses.raw_sensor_data import RawSensorData

T = TypeVar("T")


# WARNING: DEPRECATED - NOT USED ANYMORE NEED TO REMOVE IT
class TupleAdapter(SerializationAdapter):
    """Adapter for converting dataclasses to/from tuples.

    Works generically for any dataclass:
    - Dump: Uses dataclasses.astuple() to extract field values. Special handling for Topics.
    - Load: Uses unpacking cls(*values) with __post_init__ for type coercion.
    """

    @override
    def dump(self, obj: Any) -> tuple:
        """Serialize dataclass to tuple.

        Uses standard library astuple() which works for any dataclass.
        Enums automatically serialize to their values.
        Special handling for Topics to convert to string value explicitly.

        Parameters
        ----------
        obj : Any
            Dataclass instance to serialize.

        Returns
        -------
        tuple
            Tuple of field values in dataclass definition order.
        """
        if isinstance(obj, RawSensorData):
            d = asdict(obj)
            d["topic"] = obj.topic.value
            return tuple(d.values())
        return astuple(obj)

    @override
    def load(self, cls: type[T], data: tuple) -> T:
        """Deserialize tuple to dataclass.

        Uses unpacking (cls(*values)) which relies on __post_init__ for
        type coercion (e.g., string → enum conversion).

        Parameters
        ----------
        cls : type[T]
            Target dataclass class.
        data : tuple or None
            Tuple of values or None.

        Returns
        -------
        T
            Deserialized dataclass instance

        Raises
        ------
        TypeError
            If data is None or empty.
        """
        if not data:
            raise (TypeError(f"TupleAdapter cannot load {cls.__name__} from None or empty data"))
        # __post_init__ will handle type coercion for Topics (string -> enum)
        return cls(*data)
