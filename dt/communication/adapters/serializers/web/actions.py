from __future__ import annotations

from typing import Any

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.web.base import WebSerializer
from dt.communication.dataclasses.controller.action_command import ActionCommand


@serializes(ActionCommand, "web")
class ActionCommandWebSerializer(WebSerializer[ActionCommand]):
    def dump(self, obj: ActionCommand) -> Any:
        payload = self._generic.dump(obj)
        if not isinstance(payload, dict):
            return payload

        return self.convert_timestamp_field(payload, "event_at")
