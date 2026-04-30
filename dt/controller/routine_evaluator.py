"""Routine evaluation helpers.

Pure decision logic for flat compiled rules.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Optional

from dt.communication.dataclasses.controller import (ActionCommand,
                                                     CompiledRule, Trigger)
from dt.controller.action_keys import build_action_key
from dt.utils.ids import new_correlation_id


class RoutineEvaluator:
    """Evaluate compiled routine rules for current runtime state."""

    def evaluate_actions(
        self,
        rule: CompiledRule,
        plant_id: int,
        routine_id: int,
        correlation_id: str | None = None,
    ) -> list[ActionCommand]:
        commands = []
        # If correlation_id is not provided, generate a new one for this batch
        batch_correlation_id = correlation_id or str(uuid.uuid4())

        for action in rule.actions:
            actuator_id = action.actuator_id
            if actuator_id is None:
                continue

            command = action.command or "OFF"
            action_key = build_action_key(
                source="routine",
                plant_id=plant_id,
                actuator_id=actuator_id,
                command=command,
                routine_id=routine_id,
            )

            commands.append(
                ActionCommand(
                    plant_id=plant_id,
                    execution_id=new_correlation_id(),
                    action_id=action_key,
                    actuator_id=actuator_id,
                    event_at=time.time(),
                    duration=float(action.duration),
                    command=command,
                    reason=f"Routine {routine_id} triggered",
                    correlation_id=batch_correlation_id,
                    source="routine",
                    routine_id=routine_id,
                )
            )
        return commands

    def compare(self, value, operator: Optional[str], threshold) -> bool:
        if operator is None:
            return False
        if operator == "=":
            return value == threshold
        if operator == "!=":
            return value != threshold
        if operator == ">":
            return value > threshold
        if operator == "<":
            return value < threshold
        if operator == ">=":
            return value >= threshold
        if operator == "<=":
            return value <= threshold
        if operator == "==":
            return value == threshold
        return False

    def trigger_matches(
        self,
        trigger: Trigger,
        topic: Optional[str],
        value: Optional[float],
        now: datetime,
    ) -> bool:
        trigger_type = trigger.type
        if trigger_type == "sensor":
            if topic is None or value is None:
                return False
            if trigger.topic != topic:
                return False
            return self.compare(value, trigger.op, trigger.value)

        if trigger_type in {"time", "date", "interval"}:
            return False

        return False
