from typing import Any, TypeVar

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.base import Serializer
from dt.communication.adapters.serializers.generic.base import \
    GenericSerializer

T = TypeVar("T")


@serializes(Any, "spark_row")
class SparkSerializer(Serializer[T]):
    def __init__(self) -> None:
        self._generic = GenericSerializer()

    def dump(self, obj: T) -> Any:
        from pyspark.sql import Row

        return Row(**self._generic.dump(obj))

    def load(self, cls: type[T], data: Any) -> T:
        return self._generic.load(cls, self._row_to_dict(data))

    def _row_to_dict(self, row: Any) -> dict:
        if hasattr(row, "asDict"):
            # Driver context: Actual Spark Row objects
            return row.asDict()
        if hasattr(row, "_asdict"):
            # Worker context: Pandas namedtuples from vectorized execution
            return row._asdict()
        raise TypeError(f"Cannot convert {type(row)} to dict")
