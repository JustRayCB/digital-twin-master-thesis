from __future__ import annotations

from typing import Any

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.web.base import WebSerializer
from dt.communication.dataclasses.aggregated_reading import AggregatedReading
from dt.communication.dataclasses.queries import ReadingsQuery


@serializes(AggregatedReading, "web")
class AggregatedReadingWebSerializer(WebSerializer[AggregatedReading]):
    def dump(self, obj: AggregatedReading) -> Any:
        payload = self._generic.dump(obj)
        if not isinstance(payload, dict):
            return payload

        return self.convert_timestamp_field(payload, "bucket")


@serializes(ReadingsQuery, "web")
class ReadingsQueryWebSerializer(WebSerializer[ReadingsQuery]):
    def load(self, cls: type[ReadingsQuery], data: Any) -> ReadingsQuery:
        query = self._generic.load(cls, data)
        if query.since is not None:
            query.since = self.browser_time_to_seconds(query.since)
        if query.until is not None:
            query.until = self.browser_time_to_seconds(query.until)
        return query
