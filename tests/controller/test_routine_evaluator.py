"""Tests for routine evaluation logic."""

from datetime import datetime, timezone

from dt.communication.dataclasses.controller import Action, CompiledRule, Trigger
from dt.communication.topics import Topics
from dt.controller.action_keys import build_action_key
from dt.controller.routine_evaluator import RoutineEvaluator


def test_evaluate_actions_builds_commands_with_shared_correlation_id() -> None:
    """Build action commands from a compiled rule.

    Returns
    -------
    None
        Assertions fail if command construction regresses.
    """
    rule = CompiledRule(
        id="rule-1",
        trigger=Trigger(type="sensor", topic=Topics.TEMPERATURE, op=">", value=30.0),
        actions=[
            Action(actuator_id=4, command="ON", duration=10.0),
            Action(actuator_id=5, command="OFF", duration=0.0),
        ],
    )

    evaluator = RoutineEvaluator()
    commands = evaluator.evaluate_actions(rule, plant_id=1, routine_id=9, correlation_id="corr-1")

    assert len(commands) == 2
    assert {cmd.correlation_id for cmd in commands} == {"corr-1"}
    assert commands[0].action_id == build_action_key(
        source="routine",
        plant_id=1,
        actuator_id=4,
        command="ON",
        routine_id=9,
    )


def test_trigger_matches_sensor_values() -> None:
    """Match sensor triggers when topic and operator conditions are met.

    Returns
    -------
    None
        Assertions fail if trigger matching logic regresses.
    """
    trigger = Trigger(type="sensor", topic=Topics.HUMIDITY, op=">=", value=55.0)

    evaluator = RoutineEvaluator()
    matches = evaluator.trigger_matches(
        trigger=trigger,
        topic=Topics.HUMIDITY,
        value=60.0,
        now=datetime.now(timezone.utc),
    )

    assert matches is True
