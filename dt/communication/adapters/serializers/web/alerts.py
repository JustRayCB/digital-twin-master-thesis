from __future__ import annotations

from typing import Any

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.web.base import WebSerializer
from dt.communication.dataclasses.alerts.alert_record import AlertHistoryEvent


@serializes(AlertHistoryEvent, "web")
class AlertHistoryEventWebSerializer(WebSerializer[AlertHistoryEvent]):
    def dump(self, obj: AlertHistoryEvent) -> Any:
        payload = self._generic.dump(obj)
        if not isinstance(payload, dict):
            return payload

        payload["time"] = self.seconds_to_browser_time(payload.pop("timestamp"))
        payload["acknowledged_time"] = self.seconds_to_browser_time(payload.pop("acknowledged_ts"))
        payload["cleared_time"] = self.seconds_to_browser_time(payload.pop("cleared_ts"))
        return payload
