"""Serialization adapters for different target formats.

Provides a clean API for serializing/deserializing dataclasses to various formats:
- generic: Python native types (dict/list/str) for JSON/Kafka/REST
- db_row: Database row format (PostgreSQL/TimescaleDB)
- tuple: Python tuples for Spark state storage
- spark_row: PySpark Row objects for Spark DataFrames

Usage
-----
>>> from dt.communication.adapters import dump, load
>>>
>>> # Serialize to JSON-safe dict
>>> data = dump("generic", sensor_reading)
>>>
>>> # Deserialize from dict
>>> sensor = load("generic", RawSensorData, data)
>>>
>>> # Database row format
>>> row = dump("db_row", processed_data)
>>> obj = load("db_row", ProcessedSensorData, db_row)
"""

from dt.communication.adapters.base import SerializationAdapter
from dt.communication.adapters.db_row import DbRowAdapter
from dt.communication.adapters.generic import GenericAdapter
from dt.communication.adapters.registry import dump, load
from dt.communication.adapters.spark_row import SparkRowAdapter
from dt.communication.adapters.tuple import TupleAdapter

__all__ = [
    # Public API (most users only need these)
    "dump",
    "load",
    # Adapter classes (for advanced usage)
    "SerializationAdapter",
    "GenericAdapter",
    "DbRowAdapter",
    "TupleAdapter",
    "SparkRowAdapter",
]
