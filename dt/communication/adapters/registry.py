from typing import Any, TypeVar

from dt.communication.adapters.serializers.generic.base import \
    GenericSerializer

T = TypeVar("T")

_generic = GenericSerializer()
_registry: dict[tuple[Any, str], Any] = {}


def serializes(target_type: type | Any, fmt: str):
    """Decorator that registers a serializer class for a given type and format.
    Use target_type=Any to register as the format default (fallback for unregistered types).
    """

    def decorator(cls):
        _registry[(target_type, fmt)] = cls()
        return cls

    return decorator


def get_adapter(fmt: str) -> Any:
    """Return the adapter instance registered for the given format."""
    if fmt == "generic":
        return _generic
    if (Any, fmt) in _registry:
        return _registry[(Any, fmt)]
    raise KeyError(f"No serializer for format {fmt!r}")


def dump(fmt: str, obj: Any) -> Any:
    """Serialize object to specified format.

    Parameters
    ----------
    format : str
        Target format: "generic", "db_row", "tuple", or "spark_row".
    obj : Any
        Object to serialize (typically a dataclass).

    Returns
    -------
    Any
        Serialized representation in target format.

    Raises
    ------
    KeyError
        If format is not registered.

    Examples
    --------
    >>> from dt.communication.adapters import dump
    >>> data = dump("generic", sensor_reading)  # → dict (JSON-safe)
    >>> row = dump("db_row", sensor_reading)    # → dict (DB format)
    >>> tup = dump("tuple", sensor_reading)     # → tuple (Spark state)
    """
    # TEMP fix to avoid circular imports, should be refactored to avoid this
    import dt.communication.adapters.serializers.db
    import dt.communication.adapters.serializers.spark
    import dt.communication.adapters.serializers.tuple

    if fmt == "generic":
        return _generic.dump(obj)
    key = (type(obj), fmt)
    if key in _registry:
        return _registry[key].dump(obj)
    if (
        Any,
        fmt,
    ) in _registry:  # Default serializer for this format (fallback for unregistered types)
        return _registry[(Any, fmt)].dump(obj)
    raise KeyError(f"No serializer for ({type(obj).__name__!r}, {fmt!r})")


def load(fmt: str, cls: type[T], data: Any) -> T:
    """Deserialize data from specified format.

    Parameters
    ----------
    format : str
        Source format: "generic", "db_row", "tuple", or "spark_row".
    cls : type[T]
        Target class to deserialize into.
    data : Any
        Data in source format.

    Returns
    -------
    T
        Deserialized object instance.

    Raises
    ------
    KeyError
        If format is not registered.

    Examples
    --------
    >>> from dt.communication.adapters import load
    >>> sensor = load("generic", RawSensorData, json_dict)
    >>> sensor = load("db_row", ProcessedSensorData, db_row)
    >>> sensor = load("tuple", RawSensorData, tuple_data)
    """
    # TEMP fix to avoid circular imports, should be refactored to avoid this
    import dt.communication.adapters.serializers.db
    import dt.communication.adapters.serializers.spark
    import dt.communication.adapters.serializers.tuple

    if fmt == "generic":
        return _generic.load(cls, data)
    key = (cls, fmt)
    if key in _registry:
        return _registry[key].load(cls, data)
    if (
        Any,
        fmt,
    ) in _registry:  # Default serializer for this format (fallback for unregistered types)
        return _registry[(Any, fmt)].load(cls, data)
    raise KeyError(f"No serializer for ({cls.__name__!r}, {fmt!r})")
