from __future__ import annotations

from datetime import datetime
from typing import Any

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.db.base import DbSerializer
from dt.communication.dataclasses.controller import (ActionCommand,
                                                     ActuatorConfig,
                                                     ActuatorConfigSet,
                                                     ControlMode,
                                                     PlantActuatorConfig,
                                                     Routine, RoutineUpdate)


@serializes(RoutineUpdate, "db_row")
@serializes(Routine, "db_row")
class RoutineDbSerializer(DbSerializer[Routine | RoutineUpdate]):
    def dump(self, obj: Routine | RoutineUpdate) -> dict[str, Any]:
        data = self._generic.dump(obj)
        return self._dump_routine_payload(data)

    def load(self, cls: type[Routine | RoutineUpdate], data: Any) -> Routine | RoutineUpdate:
        row_dict = data._asdict()

        graph_payload = row_dict.pop("graph", None)
        compiled_payload = row_dict.get("compiled_rules")
        row_dict["graph"] = self._load_json_value(graph_payload)
        row_dict["compiled_rules"] = self._load_json_value(compiled_payload, fallback=None)

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
            data["graph"] = self._dump_json_value(graph_payload)

        compiled_payload = data.get("compiled_rules")
        if compiled_payload is not None:
            compiled_payload = self._load_json_value(compiled_payload, fallback=None)
            if compiled_payload is None:
                raise ValueError("compiled_rules must be valid JSON")
            data["compiled_rules"] = self._dump_json_value(compiled_payload)

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
        row_dict["event_at"] = self._to_unix(row_dict.get("event_at"))
        return self._generic.load(cls, row_dict)


@serializes(ActuatorConfigSet, "db_row")
class ActuatorConfigSetDbSerializer(DbSerializer[ActuatorConfigSet]):
    def dump(self, obj: ActuatorConfigSet) -> dict[str, Any]:
        return self._generic.dump(obj)

    def load(self, cls: type[ActuatorConfigSet], data: Any) -> ActuatorConfigSet:
        if not isinstance(data, list):
            raise TypeError(f"Expected a list of rows for {cls.__name__}")

        config_set = ActuatorConfigSet()
        for r in data:
            row_dict = r._asdict()
            plant_id = row_dict.get("plant_id", None)
            actuator_name = row_dict.get("actuator_name", None)
            config = ActuatorConfig(
                max_duration_seconds=row_dict.get("max_duration_seconds", None),
                min_cooldown_seconds=row_dict.get("min_cooldown_seconds", None),
                allow_overlap=row_dict.get("allow_overlap", None),
                allowed_commands=row_dict.get("allowed_commands", None),
            )
            if plant_id is None and actuator_name is None:
                config_set.defaults = config
            elif plant_id is None and actuator_name is not None:
                config_set.actuators[actuator_name] = config
            elif plant_id is not None and actuator_name is not None:
                plant_key = str(plant_id)
                if plant_key not in config_set.plants:
                    config_set.plants[plant_key] = PlantActuatorConfig()
                config_set.plants[plant_key].actuators[actuator_name] = config
        return config_set
