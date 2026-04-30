from __future__ import annotations

from typing import Any

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.web.base import WebSerializer
from dt.communication.dataclasses.queries import ForecastHistoryQuery, HealthHistoryQuery


class AnalyticsHistoryQueryWebSerializer(WebSerializer[Any]):
    def load(self, cls: type[Any], data: Any) -> Any:
        query = self._generic.load(cls, data)
        if query.since is not None:
            query.since = self.browser_time_to_seconds(query.since)
        if query.until is not None:
            query.until = self.browser_time_to_seconds(query.until)
        return query


@serializes(HealthHistoryQuery, "web")
class HealthHistoryQueryWebSerializer(AnalyticsHistoryQueryWebSerializer):
    pass


@serializes(ForecastHistoryQuery, "web")
class ForecastHistoryQueryWebSerializer(AnalyticsHistoryQueryWebSerializer):
    pass
