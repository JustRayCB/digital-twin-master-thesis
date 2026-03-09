"""Shared fixtures for controller tests."""

from __future__ import annotations

import time
import uuid
from collections.abc import Generator

import pytest
from kafka import KafkaConsumer

from dt.communication.db_client import DatabaseApiClient
from dt.communication.messaging_service import KafkaService
from dt.communication.topics import Topics
from dt.controller.actuator_manager import ActuatorManager
from dt.controller.kinds.base_actuator import BaseActuator
from dt.controller.policies import PolicyManager
from dt.data.database.consumer import setup_bridge
from tests.helpers import create_topic_consumer


class RecordingDriver:
    """Record actuator commands for assertions."""

    def __init__(self) -> None:
        self.commands: list[str] = []

    def execute(self, command: str) -> bool:
        self.commands.append(command)
        return True

    def cleanup(self) -> None:
        return None


class FailingDriver:
    """Reject all actuator commands for failure-path assertions."""

    def execute(self, command: str) -> bool:
        return False

    def cleanup(self) -> None:
        return None


@pytest.fixture
def controller_database_client(
    database_service_base_url: str, controller_database_bridge: KafkaService
) -> DatabaseApiClient:
    """Create a DatabaseApiClient for the controller tests.

    Parameters
    ----------
    database_service_base_url : str
        Base URL for the database service test instance.

    Returns
    -------
    DatabaseApiClient
        Client bound to the test database service.
    """
    return DatabaseApiClient(base_url=database_service_base_url)


@pytest.fixture(scope="module")
def controller_database_bridge(
    kafka_bootstrap_servers: str,
    shared_storage,
    kafka_topics: list[str],
) -> Generator[KafkaService, None, None]:
    """Run the database Kafka bridge for controller integration tests."""
    del kafka_topics
    config = type("TestConfig", (), {"KAFKA_URL": kafka_bootstrap_servers})
    bridge = setup_bridge(config=config, storage=shared_storage)

    deadline = time.time() + 15.0
    while time.time() < deadline:
        if bridge.consumer is not None:
            subscription = bridge.consumer.subscription()
            if Topics.ACTIONS in subscription and bridge.consumer.assignment():
                break
        time.sleep(0.25)
    else:
        bridge.disconnect()
        raise TimeoutError("Database bridge did not receive Kafka assignment")

    try:
        yield bridge
    finally:
        bridge.disconnect()


@pytest.fixture
def action_consumer(
    kafka_bootstrap_servers: str, kafka_topics: list[str]
) -> Generator[KafkaConsumer, None, None]:
    """Provide a Kafka consumer for action events.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap server URL.
    kafka_topics : list[str]
        Topics created or confirmed for controller tests.

    Returns
    -------
    Generator[KafkaConsumer, None, None]
        Kafka consumer subscribed to the actions topic.
    """
    consumer = create_topic_consumer(
        Topics.ACTIONS,
        kafka_bootstrap_servers,
        group_prefix="controller-actions",
    )
    yield consumer
    consumer.close()


@pytest.fixture
def plant_id(test_storage) -> int:
    """Create a plant record for controller tests.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    int
        Plant identifier.
    """
    return test_storage.upsert_plant(
        name=f"Controller Plant {uuid.uuid4().hex[:8]}",
        notes="Controller tests",
    )


@pytest.fixture
def recording_driver() -> RecordingDriver:
    """Create a recording actuator driver.

    Returns
    -------
    RecordingDriver
        Driver that captures executed commands.
    """
    return RecordingDriver()


@pytest.fixture
def failing_driver() -> FailingDriver:
    """Create a driver that reports hardware failure."""
    return FailingDriver()


@pytest.fixture
def policy_config_path(tmp_path) -> str:
    """Create a temporary actuator policy configuration file.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory provided by pytest.

    Returns
    -------
    str
        Path to the temporary policy configuration file.
    """
    policy_yaml = """
defaults:
  max_duration_seconds: 30
  min_cooldown_seconds: 0
  allow_overlap: false
  allowed_commands: ["ON", "OFF", "BOOST"]
actuators:
  pump:
    max_duration_seconds: 5
    min_cooldown_seconds: 2
"""
    config_path = tmp_path / "actuator_policies.yml"
    config_path.write_text(policy_yaml)
    return str(config_path)


@pytest.fixture
def policy_manager(policy_config_path: str) -> PolicyManager:
    """Create a PolicyManager backed by the test configuration file.

    Parameters
    ----------
    policy_config_path : str
        Path to the policy configuration file.

    Returns
    -------
    PolicyManager
        Policy manager loading the test config.
    """
    return PolicyManager(config_path=policy_config_path)


@pytest.fixture
def test_actuator(plant_id: int, recording_driver: RecordingDriver) -> BaseActuator:
    """Create a test actuator bound to the recording driver.

    Parameters
    ----------
    plant_id : int
        Plant identifier for the actuator.
    recording_driver : RecordingDriver
        Driver capturing actuator commands.

    Returns
    -------
    BaseActuator
        Actuator instance with a recording driver.
    """
    return BaseActuator(
        actuator_id=-1,
        name="pump",
        plant_id=plant_id,
        driver=recording_driver,
        pin=17,
        relay_channel=1,
    )


@pytest.fixture
def failing_actuator(plant_id: int, failing_driver: FailingDriver) -> BaseActuator:
    """Create a test actuator backed by a failing driver."""
    return BaseActuator(
        actuator_id=-1,
        name="pump",
        plant_id=plant_id,
        driver=failing_driver,
        pin=17,
        relay_channel=1,
    )


@pytest.fixture
def actuator_manager(
    kafka_service: KafkaService,
    controller_database_client: DatabaseApiClient,
    test_actuator: BaseActuator,
    policy_manager: PolicyManager,
) -> ActuatorManager:
    """Create an actuator manager with a bound actuator.

    Parameters
    ----------
    kafka_service : KafkaService
        Messaging service for action publishing.
    controller_database_client : DatabaseApiClient
        Database API client for actuator bindings and logging.
    test_actuator : BaseActuator
        Actuator instance to bind.

    Returns
    -------
    ActuatorManager
        Manager with a bound actuator ready for execution.
    """
    manager = ActuatorManager(
        actuators={},
        policy_manager=policy_manager,
        messaging_service=kafka_service,
        database_client=controller_database_client,
    )
    manager.add_actuator(test_actuator)
    return manager


@pytest.fixture
def failing_actuator_manager(
    kafka_service: KafkaService,
    controller_database_client: DatabaseApiClient,
    failing_actuator: BaseActuator,
    policy_manager: PolicyManager,
) -> ActuatorManager:
    """Create an actuator manager with a failing actuator."""
    manager = ActuatorManager(
        actuators={},
        policy_manager=policy_manager,
        messaging_service=kafka_service,
        database_client=controller_database_client,
    )
    manager.add_actuator(failing_actuator)
    return manager


@pytest.fixture
def bound_actuator(actuator_manager: ActuatorManager, test_actuator: BaseActuator) -> BaseActuator:
    """Return the actuator after it has been bound to the database.

    Parameters
    ----------
    actuator_manager : ActuatorManager
        Manager that performed the binding.
    test_actuator : BaseActuator
        Actuator instance to return.

    Returns
    -------
    BaseActuator
        Bound actuator with an assigned ID.
    """
    return test_actuator


@pytest.fixture
def controller_service(
    controller_database_client: DatabaseApiClient,
    kafka_service: KafkaService,
    actuator_manager: ActuatorManager,
    policy_manager: PolicyManager,
):
    """Create a controller service wired to test dependencies.

    Parameters
    ----------
    controller_database_client : DatabaseApiClient
        Database client bound to the test service.
    kafka_service : KafkaService
        Kafka messaging service for publishing actions.
    actuator_manager : ActuatorManager
        Manager with bound actuators.

    Returns
    -------
    ControllerService
        Controller service instance for tests.
    """
    from dt.controller.service import ControllerService

    return ControllerService(
        database_client=controller_database_client,
        messaging_service=kafka_service,
        actuator_manager=actuator_manager,
        policy_manager=policy_manager,
    )
