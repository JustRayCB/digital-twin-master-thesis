from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.db.base import DbSerializer
from dt.communication.dataclasses.controller import (ActionCommand,
                                                     ControlMode, Routine,
                                                     RoutineUpdate)


@serializes(Routine, "db_row")
class RoutineDbSerializer(DbSerializer[Routine | RoutineUpdate]):
    def dump(self, obj: Routine | RoutineUpdate) -> dict[str, Any]:
        data = self._generic.dump(obj)
        return self._dump_routine_payload(data)

    def load(self, cls: type[Routine | RoutineUpdate], data: Any) -> Routine | RoutineUpdate:
        row_dict = data._asdict()

        graph_payload = row_dict.pop("graph", None)
        compiled_payload = row_dict.get("compiled_rules")
        if isinstance(compiled_payload, str):
            try:
                compiled_payload = json.loads(compiled_payload)
            except json.JSONDecodeError:
                compiled_payload = None
        row_dict["graph"] = graph_payload
        row_dict["compiled_rules"] = compiled_payload

        created_at = row_dict.get("created_at")
        if isinstance(created_at, datetime):
            row_dict["created_at"] = created_at.isoformat()
        updated_at = row_dict.get("updated_at")
        if isinstance(updated_at, datetime):
            row_dict["updated_at"] = updated_at.isoformat()

        if cls is Routine:
            return self._generic.load(Routine, row_dict)
        return self._generic.load(RoutineUpdate, row_dict)

    def _dump_routine_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        graph_payload = data.pop("graph", None)
        if graph_payload is not None:
            data["graph"] = json.dumps(graph_payload)

        compiled_payload = data.get("compiled_rules")
        if compiled_payload is not None:
            if isinstance(compiled_payload, str):
                try:
                    compiled_payload = json.loads(compiled_payload)
                except json.JSONDecodeError as exc:
                    raise ValueError("compiled_rules must be valid JSON") from exc
            data["compiled_rules"] = json.dumps(compiled_payload)

        return data


@serializes(ControlMode, "db_row")
class ControlModeDbSerializer(DbSerializer[ControlMode]):
    def dump(self, obj: ControlMode) -> dict[str, Any]:
        data = self._generic.dump(obj)
        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            try:
                data["updated_at"] = datetime.fromisoformat(updated_at)
            except ValueError:
                pass
        return data

    def load(self, cls: type[ControlMode], data: Any) -> ControlMode:
        row_dict = data._asdict()
        updated_at = row_dict.get("updated_at")
        if isinstance(updated_at, datetime):
            row_dict["updated_at"] = updated_at.isoformat()
        elif isinstance(updated_at, str):
            try:
                row_dict["updated_at"] = datetime.fromisoformat(updated_at).isoformat()
            except ValueError:
                pass
        return self._generic.load(cls, row_dict)


@serializes(ActionCommand, "db_row")
class ActionCommandDbSerializer(DbSerializer[ActionCommand]):
    def dump(self, obj: ActionCommand) -> dict[str, Any]:
        data = self._generic.dump(obj)
        return data

    def load(self, cls: type[ActionCommand], data: Any) -> ActionCommand:
        row_dict = data._asdict()
        row_dict["started_at"] = self._to_unix(row_dict.get("started_at"))
        row_dict["ended_at"] = self._to_unix(row_dict.get("ended_at"))
        return self._generic.load(cls, row_dict)
