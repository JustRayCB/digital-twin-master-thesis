"""Integration tests for controller service behavior."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest
from kafka import KafkaConsumer

from dt.communication.adapters import load
from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.controller import (Action, ActionCommand,
                                                     ActionDispatch,
                                                     ControlMode, Routine,
                                                     RoutineEdge, RoutineGraph,
                                                     RoutineNode,
                                                     RoutineUpdate, Trigger)
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.db_client import DatabaseApiClient
from dt.communication.topics import Topics
from dt.controller.service import ControllerService
from tests.controller.helpers import poll_action_messages, wait_for_action_history

pytestmark = [pytest.mark.requires_kafka, pytest.mark.requires_timescale]


def _build_sensor_routine_graph(plant_id: int, actuator_id: int, name: str) -> RoutineGraph:
    """Build a sensor-trigger routine graph for controller service tests."""
    return RoutineGraph(
        name=name,
        plant_id=plant_id,
        nodes=[
            RoutineNode(
                id="trigger-1",
                kind="trigger",
                trigger=Trigger(type="sensor", topic=Topics.TEMPERATURE, op=">", value=20.0),
            ),
            RoutineNode(
                id="action-1",
                kind="action",
                action=Action(
                    actuator_id=actuator_id,
                    command="ON",
                    duration=0.0,
                ),
            ),
        ],
        edges=[RoutineEdge(source="trigger-1", target="action-1")],
    )


def _build_interval_routine_graph(
    plant_id: int, actuator_id: int, at: str, name: str
) -> RoutineGraph:
    """Build an interval-trigger routine graph for controller service tests."""
    return RoutineGraph(
        name=name,
        plant_id=plant_id,
        nodes=[
            RoutineNode(
                id="trigger-1",
                kind="trigger",
                trigger=Trigger(type="interval", every_days=1, at=at),
            ),
            RoutineNode(
                id="action-1",
                kind="action",
                action=Action(
                    actuator_id=actuator_id,
                    command="ON",
                    duration=0.0,
                ),
            ),
        ],
        edges=[RoutineEdge(source="trigger-1", target="action-1")],
    )


def test_dispatch_action_logs_and_publishes(
    controller_service: ControllerService,
    controller_database_client: DatabaseApiClient,
    bound_actuator,
    recording_driver,
    action_consumer: KafkaConsumer,
) -> None:
    """Dispatch a manual action and verify persistence, Kafka publish, and actuator execution."""
    payload = ActionDispatch(
        plant_id=bound_actuator.plant_id,
        actuator_id=bound_actuator.actuator_id,
        command="ON",
        source="manual",
        duration=0.0,
        reason="Manual test dispatch",
    )

    response = controller_service.dispatch_action(payload)

    assert response["status"] == "accepted"
    action_id = response["action_id"]

    wait_for_action_history(
        controller_database_client,
        bound_actuator.plant_id,
        lambda items: any(
            item.action_id == action_id and item.status == "completed" for item in items
        ),
        limit=5,
    )

    messages = poll_action_messages(
        action_consumer, expected_count=2, timeout_seconds=5.0, action_id=action_id
    )

    assert recording_driver.commands == ["ON"]
    assert [message["status"] for message in messages] == ["running", "completed"]
    action_events = [load("generic", ActionCommand, message) for message in messages]
    assert [event.action_id for event in action_events] == [action_id, action_id]


def test_routine_actions_skip_when_ai_autopilot_enabled(
    controller_service: ControllerService,
    controller_database_client: DatabaseApiClient,
    bound_actuator,
    recording_driver,
    action_consumer: KafkaConsumer,
) -> None:
    """Skip routine actions when AI auto-pilot mode is enabled."""
    controller_database_client.set_mode(
        ControlMode(
            plant_id=bound_actuator.plant_id,
            ai_autopilot_enabled=True,
            owner="ai",
        )
    )

    graph = _build_sensor_routine_graph(
        plant_id=bound_actuator.plant_id,
        actuator_id=bound_actuator.actuator_id,
        name="Autopilot Test",
    )

    controller_service.create_routine(
        RoutineUpdate(plant_id=bound_actuator.plant_id, name="Autopilot Test", graph=graph)
    )

    controller_service.evaluate_routines_for_sensor(
        ProcessedSensorData(
            plant_id=bound_actuator.plant_id,
            sensor_id=1,
            timestamp=time.time(),
            value=25.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="corr-autopilot",
            flags={ValidationFlag.VALID: True},
            dq_score=1.0,
            imputed=False,
        )
    )

    history = wait_for_action_history(
        controller_database_client,
        bound_actuator.plant_id,
        lambda items: any(
            item.status == "skipped"
            and item.error_message == "Routine suspended while AI auto-pilot mode is enabled"
            for item in items
        ),
        limit=5,
    )
    skipped = next(item for item in history if item.status == "skipped")

    messages = poll_action_messages(
        action_consumer,
        expected_count=1,
        timeout_seconds=5.0,
        action_id=skipped.action_id,
    )

    assert recording_driver.commands == []
    assert [message["status"] for message in messages] == ["skipped"]


def test_time_interval_trigger_executes_actions(
    controller_service: ControllerService,
    controller_database_client: DatabaseApiClient,
    bound_actuator,
    recording_driver,
    action_consumer: KafkaConsumer,
) -> None:
    """Execute interval-triggered actions when scheduled time matches."""
    now = datetime.now(controller_service._timezone)
    trigger_time = now.strftime("%H:%M")
    graph = _build_interval_routine_graph(
        plant_id=bound_actuator.plant_id,
        actuator_id=bound_actuator.actuator_id,
        at=trigger_time,
        name="Interval Routine",
    )

    routine_id = controller_service.create_routine(
        RoutineUpdate(plant_id=bound_actuator.plant_id, name="Interval Routine", graph=graph)
    )

    last_check = now - timedelta(minutes=2)
    controller_service.evaluate_time_triggers(bound_actuator.plant_id, last_check, now)

    history = wait_for_action_history(
        controller_database_client,
        bound_actuator.plant_id,
        lambda items: any(
            item.routine_id == routine_id and item.status == "completed" for item in items
        ),
    )
    completed = next(
        item for item in history if item.routine_id == routine_id and item.status == "completed"
    )

    messages = poll_action_messages(
        action_consumer,
        expected_count=2,
        timeout_seconds=5.0,
        action_id=completed.action_id,
    )

    assert recording_driver.commands == ["ON"]
    assert [message["status"] for message in messages] == ["running", "completed"]
    assert (routine_id, "trigger-1") in controller_service._last_fired


def test_controller_service_caches_persisted_routines_as_routine_instances(
    controller_service: ControllerService,
    controller_database_client: DatabaseApiClient,
    bound_actuator,
    recording_driver,
) -> None:
    """Load persisted routines into the cache as Routine instances before interval evaluation."""
    now = datetime.now(controller_service._timezone)
    graph = _build_interval_routine_graph(
        plant_id=bound_actuator.plant_id,
        actuator_id=bound_actuator.actuator_id,
        at=now.strftime("%H:%M"),
        name="Cached Routine",
    )

    routine_id = controller_service.create_routine(
        RoutineUpdate(plant_id=bound_actuator.plant_id, name="Cached Routine", graph=graph)
    )

    controller_service._routine_cache.clear()
    cached_routines = controller_service._get_routines(bound_actuator.plant_id)

    assert cached_routines
    assert all(isinstance(item, Routine) for item in cached_routines)

    last_check = now - timedelta(minutes=2)
    controller_service.evaluate_time_triggers(bound_actuator.plant_id, last_check, now)

    wait_for_action_history(
        controller_database_client,
        bound_actuator.plant_id,
        lambda items: any(
            item.routine_id == routine_id and item.status == "completed" for item in items
        ),
    )

    assert recording_driver.commands == ["ON"]
    assert (routine_id, "trigger-1") in controller_service._last_fired
