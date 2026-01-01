"""Adapter registry providing clean serialization API.

This module provides simple dump() and load() functions that route to
the appropriate adapter based on the format string.
"""

from typing import Any, TypeVar

from dt.communication.adapters.db_row import DbRowAdapter
from dt.communication.adapters.generic import GenericAdapter
from dt.communication.adapters.spark_row import SparkRowAdapter
from dt.communication.adapters.tuple import TupleAdapter

T = TypeVar("T")

ADAPTERS = {
    "generic": GenericAdapter(),
    "db_row": DbRowAdapter(),
    "tuple": TupleAdapter(),
    "spark_row": SparkRowAdapter(),
}

def get_adapter(format: str):
    """Return the adapter instance registered for the given format."""
    if format not in ADAPTERS:
        raise KeyError(f"Unknown format: {format}. Available formats: {', '.join(ADAPTERS.keys())}")
    return ADAPTERS[format]


def dump(format: str, obj: Any) -> Any:
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
    if format not in ADAPTERS:
        raise KeyError(
            f"Unknown format: {format}. " f"Available formats: {', '.join(ADAPTERS.keys())}"
        )
    return ADAPTERS[format].dump(obj)


def load(format: str, cls: type[T], data: Any) -> T:
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
    if format not in ADAPTERS:
        raise KeyError(
            f"Unknown format: {format}. " f"Available formats: {', '.join(ADAPTERS.keys())}"
        )
    return ADAPTERS[format].load(cls, data)
