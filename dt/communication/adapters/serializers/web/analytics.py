from __future__ import annotations

from typing import Any

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.web.base import WebSerializer
from dt.communication.dataclasses.queries import (AnalyticsExportQuery,
                                                  ForecastHistoryQuery,
                                                  HealthHistoryQuery,
                                                  RecommendationHistoryQuery)


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


@serializes(RecommendationHistoryQuery, "web")
class RecommendationHistoryQueryWebSerializer(AnalyticsHistoryQueryWebSerializer):
    pass


@serializes(AnalyticsExportQuery, "web")
class AnalyticsExportQueryWebSerializer(AnalyticsHistoryQueryWebSerializer):
    def load(self, cls: type[AnalyticsExportQuery], data: Any) -> AnalyticsExportQuery:
        payload = {key: data[key] for key in ("plant_id", "since", "until", "limit") if key in data}
        if payload.get("since") in (None, ""):
            payload.pop("since", None)
        else:
            payload["since"] = self.browser_time_to_seconds(payload["since"])
        if payload.get("until") in (None, ""):
            payload.pop("until", None)
        else:
            payload["until"] = self.browser_time_to_seconds(payload["until"])
        if payload.get("limit") in (None, ""):
            payload.pop("limit", None)
        return cls(**payload)

    def dump(self, obj: AnalyticsExportQuery) -> dict[str, Any]:
        payload = self._generic.dump(obj)
        payload["since"] = self.seconds_to_browser_time(payload.get("since"))
        payload["until"] = self.seconds_to_browser_time(payload.get("until"))
        payload["limit"] = obj.effective_limit
        return payload
