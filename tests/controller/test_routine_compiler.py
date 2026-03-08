"""Tests for routine compilation logic."""

import pytest

from dt.communication.dataclasses.controller import (
    Action,
    RoutineEdge,
    RoutineGraph,
    RoutineNode,
    Trigger,
)
from dt.communication.topics import Topics
from dt.controller.routine_compiler import RoutineCompiler


def test_compile_builds_rules_for_reachable_actions() -> None:
    """Compile a graph with a reachable action.

    Returns
    -------
    None
        Assertions fail if compilation output regresses.
    """
    graph = RoutineGraph(
        name="Morning Routine",
        plant_id=1,
        nodes=[
            RoutineNode(
                id="trigger-1",
                kind="trigger",
                trigger=Trigger(type="sensor", topic=Topics.TEMPERATURE, op=">", value=25.0),
            ),
            RoutineNode(
                id="action-1",
                kind="action",
                action=Action(actuator_id=1, command="ON", duration=5.0),
            ),
        ],
        edges=[RoutineEdge(source="trigger-1", target="action-1")],
    )

    compiled = RoutineCompiler().compile(graph)

    assert len(compiled) == 1
    rule = compiled[0]
    assert rule.trigger.type == "sensor"
    assert rule.trigger.topic == Topics.TEMPERATURE
    assert rule.actions[0].actuator_id == 1
    assert rule.actions[0].command == "ON"


def test_validate_rejects_unreachable_action() -> None:
    """Reject graphs where an action cannot be reached from any trigger.

    Returns
    -------
    None
        Assertions fail if validation stops catching unreachable actions.
    """
    graph = RoutineGraph(
        name="Broken Routine",
        plant_id=1,
        nodes=[
            RoutineNode(
                id="trigger-1",
                kind="trigger",
                trigger=Trigger(type="sensor", topic=Topics.TEMPERATURE, op=">", value=20.0),
            ),
            RoutineNode(
                id="action-1",
                kind="action",
                action=Action(actuator_id=1, command="ON", duration=5.0),
            ),
        ],
        edges=[],
    )

    with pytest.raises(ValueError, match="not reachable"):
        RoutineCompiler().validate(graph)
