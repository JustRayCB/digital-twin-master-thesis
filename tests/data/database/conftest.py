"""Shared fixtures for database service tests."""

import json
import time
import uuid
from collections.abc import Callable, Generator

import pytest
from docker import DockerClient
from docker.errors import DockerException
from kafka import KafkaAdminClient, KafkaProducer
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError
from sqlalchemy import Engine, create_engine, text
from testcontainers.kafka import KafkaContainer
from testcontainers.postgres import PostgresContainer

from dt.communication.messaging_service import KafkaService
from dt.communication.topics import Topics
from dt.data.database.app import create_app
from dt.data.database.migrations.runner import MigrationRunner
from dt.data.database.timescale_storage import TimescaleStorage
from dt.utils import Config


def wait_until(
    predicate: Callable[[], bool],
    timeout_seconds: float = 10.0,
    interval_seconds: float = 0.2,
) -> None:
    """Wait until a predicate returns True.

    Parameters
    ----------
    predicate : Callable[[], bool]
        Callback returning True when the wait condition is satisfied.
    timeout_seconds : float, optional
        Max time to wait before raising.
    interval_seconds : float, optional
        Sleep interval between predicate checks.

    Returns
    -------
    None
        Raises on timeout.
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(interval_seconds)
    raise TimeoutError("Condition was not satisfied before timeout")


def truncate_timescale_database(engine: Engine) -> None:
    """Remove all test data from the TimescaleDB schema.

    Parameters
    ----------
    engine : sqlalchemy.Engine
        SQLAlchemy engine connected to the test database.

    Returns
    -------
    None
        Truncates relational tables and hypertables for test isolation.
    """
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE plants CASCADE"))
        conn.execute(text("TRUNCATE sensor_readings_1h"))


@pytest.fixture(scope="session")
def docker_client() -> DockerClient:
    """Return a working Docker client for testcontainers.

    Returns
    -------
    DockerClient
        Docker client used by testcontainers.
    """
    try:
        import docker

        client = docker.from_env()
        client.ping()
        return client
    except DockerException as exc:
        pytest.skip(f"Docker not available for testcontainers: {exc}")


@pytest.fixture(scope="session")
def postgres_container(docker_client: DockerClient) -> Generator[PostgresContainer, None, None]:
    """Start a PostgreSQL container with TimescaleDB extension.

    Returns
    -------
    Generator[PostgresContainer, None, None]
        Running container for database integration tests.
    """
    with PostgresContainer(image="timescale/timescaledb:latest-pg18", driver="psycopg") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def db_engine(postgres_container: PostgresContainer) -> Generator[Engine, None, None]:
    """Create SQLAlchemy engine and run migrations.

    Parameters
    ----------
    postgres_container : PostgresContainer
        Running testcontainers PostgreSQL instance.

    Returns
    -------
    Generator[Engine, None, None]
        SQLAlchemy engine connected to the test database.
    """
    db_url = postgres_container.get_connection_url()
    engine = create_engine(db_url, pool_pre_ping=True)

    psycopg_url = db_url.replace("postgresql+psycopg://", "postgresql://")
    runner = MigrationRunner(migrations_dir="dt/data/database/migrations", db_url=psycopg_url)
    runner.run_migrations()

    yield engine
    engine.dispose()


@pytest.fixture
def storage(db_engine: Engine) -> TimescaleStorage:
    """Create a TimescaleStorage instance with a clean database.

    Parameters
    ----------
    db_engine : sqlalchemy.Engine
        SQLAlchemy engine connected to TimescaleDB.

    Returns
    -------
    TimescaleStorage
        Storage instance backed by a clean database schema.
    """
    truncate_timescale_database(db_engine)
    return TimescaleStorage(engine=db_engine)


@pytest.fixture
def wait_until_condition() -> Callable[..., None]:
    """Provide the `wait_until` helper as a fixture.

    Returns
    -------
    Callable[..., None]
        Wait helper used to poll for async conditions in integration tests.
    """
    return wait_until


@pytest.fixture
def client(storage: TimescaleStorage):
    """Create a Flask test client backed by the real storage implementation.

    Parameters
    ----------
    storage : TimescaleStorage
        Storage instance used by the app under test.

    Returns
    -------
    flask.testing.FlaskClient
        Client for issuing HTTP requests to the database API.
    """
    app = create_app(config=Config, storage=storage)
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def sample_plant_id(storage: TimescaleStorage) -> int:
    """Create a sample plant for database tests.

    Parameters
    ----------
    storage : TimescaleStorage
        Storage instance for persisting the sample plant.

    Returns
    -------
    int
        Plant identifier.
    """
    return storage.upsert_plant(name="Test Plant", notes="Database tests")


@pytest.fixture
def sample_sensor(storage: TimescaleStorage, sample_plant_id: int):
    """Create a sample sensor descriptor registered in the database.

    Parameters
    ----------
    storage : TimescaleStorage
        Storage instance used to register the sensor.
    sample_plant_id : int
        Plant identifier owning the sensor.

    Returns
    -------
    dt.communication.dataclasses.SensorDescriptor
        Registered sensor descriptor with ID assigned.
    """
    from dt.communication.dataclasses import SensorDescriptor

    sensor = SensorDescriptor(
        id=0,
        plant_id=sample_plant_id,
        name="test_sensor",
        pin=7,
        read_interval=60,
    )
    sensor_id = storage.register_sensor(sensor)
    sensor.id = sensor_id
    return sensor


@pytest.fixture(scope="session")
def kafka_container(docker_client: DockerClient) -> Generator[KafkaContainer, None, None]:
    """Start a Kafka container for database bridge integration tests."""
    with KafkaContainer().with_kraft() as kafka:
        yield kafka


@pytest.fixture(scope="session")
def kafka_bootstrap_servers(kafka_container: KafkaContainer) -> str:
    """Return Kafka bootstrap servers string."""
    return kafka_container.get_bootstrap_server()


@pytest.fixture(scope="session")
def kafka_topics(kafka_bootstrap_servers: str) -> list[str]:
    """Ensure required Kafka topics exist for bridge tests.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap server URL.

    Returns
    -------
    list[str]
        Topics created or confirmed for database bridge tests.
    """
    topics: set[str] = {Topics.ALERTS}
    topics.update(topic.processed for topic in Topics.list_sensor_topics())

    admin = KafkaAdminClient(
        bootstrap_servers=kafka_bootstrap_servers, client_id="database-tests-admin"
    )
    existing = set(admin.list_topics())
    to_create = [
        NewTopic(name=topic, num_partitions=1, replication_factor=1)
        for topic in topics
        if topic not in existing
    ]
    if to_create:
        try:
            admin.create_topics(to_create)
        except TopicAlreadyExistsError:
            pass
    admin.close()

    producer = KafkaProducer(
        bootstrap_servers=kafka_bootstrap_servers,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
    )
    for topic in topics:
        producer.send(topic, {})
    producer.flush()
    producer.close()

    return sorted(topics)


@pytest.fixture
def kafka_service(
    kafka_bootstrap_servers: str, kafka_topics: list[str]
) -> Generator[KafkaService, None, None]:
    """Create a KafkaService for publishing messages during bridge tests.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap server URL.
    kafka_topics : list[str]
        Ensured topics for tests.

    Returns
    -------
    Generator[KafkaService, None, None]
        Connected Kafka service.
    """
    client_id = f"database-tests-{uuid.uuid4().hex[:8]}"
    service = KafkaService(host=kafka_bootstrap_servers, client_id=client_id, group_id=client_id)
    service.connect()
    yield service
    service.disconnect()
