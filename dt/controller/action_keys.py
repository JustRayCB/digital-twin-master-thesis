from __future__ import annotations


def build_action_key(
    source: str,
    plant_id: int,
    actuator_id: int,
    command: str,
    routine_id: int | None = None,
) -> str:
    command_key = str(command).upper()
    if source == "routine":
        if routine_id is None:
            raise ValueError("routine_id is required for routine action keys")
        return f"routine:{plant_id}:{routine_id}:{actuator_id}:{command_key}"
    if source == "ai":
        return f"ai:{plant_id}:{actuator_id}:{command_key}"
    return f"manual:{plant_id}:{actuator_id}:{command_key}"
