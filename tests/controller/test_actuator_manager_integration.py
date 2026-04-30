"""Integration tests for actuator manager behavior."""

import time
import uuid

import pytest
from kafka import KafkaConsumer

from dt.communication.adapters import load
from dt.communication.dataclasses.controller import ActionCommand, ActuatorConfig, ActuatorConfigSet
from dt.communication.db_client import DatabaseApiClient
from dt.controller.actuator_manager import ActuatorManager
from tests.controller.helpers import poll_action_messages, wait_for_action_history

pytestmark = [pytest.mark.requires_kafka, pytest.mark.requires_timescale]


def _build_action(
    plant_id: int, actuator_id: int, command: str, duration: float = 0.0
) -> ActionCommand:
    """Create an ActionCommand for tests.

    Parameters
    ----------
    plant_id : int
        Plant identifier for the action.
    actuator_id : int
        Actuator identifier for the action.
    command : str
        Command to execute.
    duration : float, optional
        Command duration.

    Returns
    -------
    ActionCommand
        Action command instance.
    """
    return ActionCommand(
        plant_id=plant_id,
        execution_id=str(uuid.uuid4()),
        action_id=f"manual-test-{uuid.uuid4().hex}",
        actuator_id=actuator_id,
        event_at=time.time(),
        duration=duration,
        command=command,
        reason="Actuator manager test",
        correlation_id=str(uuid.uuid4()),
        source="manual",
    )


def test_execute_publishes_and_logs(
    actuator_manager: ActuatorManager,
    controller_database_client: DatabaseApiClient,
    bound_actuator,
    action_consumer: KafkaConsumer,
) -> None:
    """Execute an allowed command and verify persistence + Kafka publish.

    Parameters
    ----------
    actuator_manager : ActuatorManager
        Manager under test.
    controller_database_client : DatabaseApiClient
        Database API client for querying action history.
    bound_actuator : BaseActuator
        Bound actuator instance.
    action_consumer : KafkaConsumer
        Kafka consumer subscribed to the actions topic.

    Returns
    -------
    None
        Assertions fail if successful execution stops logging or publishing.
    """
    action = _build_action(bound_actuator.plant_id, bound_actuator.actuator_id, "ON")
    result = actuator_manager.execute(action)

    assert result is True

    wait_for_action_history(
        controller_database_client,
        bound_actuator.plant_id,
        lambda items: any(
            item.action_id == action.action_id and item.status == "completed" for item in items
        ),
    )

    messages = poll_action_messages(
        action_consumer, expected_count=2, timeout_seconds=5.0, action_id=action.action_id
    )

    assert [message["status"] for message in messages] == ["running", "completed"]
    published = [load("generic", ActionCommand, message) for message in messages]
    assert [event.action_id for event in published] == [action.action_id, action.action_id]


def test_execute_rejects_disallowed_command(
    actuator_manager: ActuatorManager,
    controller_database_client: DatabaseApiClient,
    bound_actuator,
    action_consumer: KafkaConsumer,
) -> None:
    """Reject commands not listed in policy allowed commands.

    Parameters
    ----------
    actuator_manager : ActuatorManager
        Manager under test.
    controller_database_client : DatabaseApiClient
        Database API client for querying action history.
    bound_actuator : BaseActuator
        Bound actuator instance.
    action_consumer : KafkaConsumer
        Kafka consumer subscribed to the actions topic.

    Returns
    -------
    None
        Assertions fail if rejection logging regresses.
    """
    action = _build_action(bound_actuator.plant_id, bound_actuator.actuator_id, "TURBO")
    result = actuator_manager.execute(action)

    assert result is False

    wait_for_action_history(
        controller_database_client,
        bound_actuator.plant_id,
        lambda items: any(
            item.action_id == action.action_id and item.status == "rejected" for item in items
        ),
    )

    messages = poll_action_messages(
        action_consumer, expected_count=2, timeout_seconds=5.0, action_id=action.action_id
    )
    assert [message["status"] for message in messages] == ["running", "rejected"]


def test_execute_enforces_cooldown(
    actuator_manager: ActuatorManager,
    controller_database_client: DatabaseApiClient,
    bound_actuator,
) -> None:
    """Reject commands when cooldown is active.

    Parameters
    ----------
    actuator_manager : ActuatorManager
        Manager under test.
    controller_database_client : DatabaseApiClient
        Database API client for querying action history.
    bound_actuator : BaseActuator
        Bound actuator instance.

    Returns
    -------
    None
        Assertions fail if cooldown enforcement regresses.
    """
    first = _build_action(bound_actuator.plant_id, bound_actuator.actuator_id, "ON")
    second = _build_action(bound_actuator.plant_id, bound_actuator.actuator_id, "ON")

    assert actuator_manager.execute(first) is True
    assert actuator_manager.execute(second) is False

    wait_for_action_history(
        controller_database_client,
        bound_actuator.plant_id,
        lambda items: any(
            item.action_id == second.action_id and item.status == "rejected" for item in items
        ),
    )


def test_execute_publishes_failed_status(
    failing_actuator_manager: ActuatorManager,
    controller_database_client: DatabaseApiClient,
    failing_actuator,
    action_consumer: KafkaConsumer,
) -> None:
    """Publish running and failed status events when hardware execution fails."""
    action = _build_action(failing_actuator.plant_id, failing_actuator.actuator_id, "ON")
    result = failing_actuator_manager.execute(action)

    assert result is False

    wait_for_action_history(
        controller_database_client,
        failing_actuator.plant_id,
        lambda items: any(
            item.action_id == action.action_id and item.status == "failed" for item in items
        ),
    )

    messages = poll_action_messages(
        action_consumer, expected_count=2, timeout_seconds=5.0, action_id=action.action_id
    )
    assert [message["status"] for message in messages] == ["running", "failed"]


def test_policy_manager_reloads_persisted_policies(
    policy_manager,
    controller_database_client: DatabaseApiClient,
) -> None:
    """Reload policies from the database service instead of a local stub."""
    persisted_config = ActuatorConfigSet()
    persisted_config.defaults = ActuatorConfig(
        max_duration_seconds=45,
        min_cooldown_seconds=1,
        allow_overlap=True,
        allowed_commands=["ON", "OFF"],
    )
    persisted_config.actuators["pump"] = ActuatorConfig(
        max_duration_seconds=9,
        min_cooldown_seconds=4,
        allow_overlap=False,
        allowed_commands=["ON"],
    )

    controller_database_client.set_policies(persisted_config)

    policy_manager.load_policies()
    policy = policy_manager.resolve(plant_id=1, actuator_name="pump")

    assert policy.max_duration_seconds == 9
    assert policy.min_cooldown_seconds == 4
    assert policy.allow_overlap is False
    assert policy.allowed_commands == ["ON"]
