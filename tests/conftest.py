"""Shared pytest fixtures for integration tests."""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Generator

import pytest
from docker.errors import DockerException
from sqlalchemy import Engine, create_engine, text
from testcontainers.kafka import KafkaContainer
from testcontainers.postgres import PostgresContainer
from werkzeug.serving import make_server

from dt.communication.messaging_service import KafkaService
from dt.communication.topics import Topics
from dt.communication.db_client import DatabaseApiClient
from dt.data.database.app import create_app
from dt.data.database.migrations.runner import MigrationRunner
from dt.data.database.timescale_storage import TimescaleStorage
from dt.utils import Config
from tests.helpers import ensure_kafka_topics


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


def require_docker() -> None:
    """Skip integration tests when Docker is not available."""
    try:
        import docker

        client = docker.from_env()
        client.ping()
    except DockerException as exc:
        pytest.skip(f"Docker not available for testcontainers: {exc}")


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Start a PostgreSQL container with TimescaleDB extension.

    Returns
    -------
    Generator[PostgresContainer, None, None]
        Running container for database integration tests.
    """
    require_docker()
    with PostgresContainer(image="timescale/timescaledb:latest-pg18", driver="psycopg") as postgres:
        time.sleep(2)
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
    runner = MigrationRunner(migrations_dir=Config.DB_MIGRATIONS_DIR, db_url=psycopg_url)
    runner.run_migrations()

    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def kafka_container() -> Generator[KafkaContainer, None, None]:
    """Start a Kafka container for integration tests."""
    require_docker()
    with KafkaContainer().with_kraft() as kafka:
        yield kafka


@pytest.fixture(scope="session")
def kafka_bootstrap_servers(kafka_container: KafkaContainer) -> str:
    """Return Kafka bootstrap servers string."""
    return kafka_container.get_bootstrap_server()


@pytest.fixture(scope="session")
def kafka_topics(kafka_bootstrap_servers: str) -> list[str]:
    """Ensure required Kafka topics exist for integration tests.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap server URL.

    Returns
    -------
    list[str]
        Topics created or confirmed for integration tests.
    """
    topics: set[str] = {Topics.ALERTS, Topics.ACTIONS}
    topics.update(topic.processed for topic in Topics.list_sensor_topics())
    return ensure_kafka_topics(kafka_bootstrap_servers, topics)


@pytest.fixture
def kafka_service(
    kafka_bootstrap_servers: str, kafka_topics: list[str]
) -> Generator[KafkaService, None, None]:
    """Create a KafkaService for publishing messages during integration tests.

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
    client_id = f"integration-tests-{uuid.uuid4().hex[:8]}"
    service = KafkaService(host=kafka_bootstrap_servers, client_id=client_id, group_id=client_id)
    service.connect()
    yield service
    service.disconnect()


@pytest.fixture(scope="module")
def shared_storage(db_engine: Engine) -> TimescaleStorage:
    """Timescale storage shared across a test module."""
    truncate_timescale_database(db_engine)
    return TimescaleStorage(engine=db_engine)


@pytest.fixture
def test_storage(db_engine: Engine) -> TimescaleStorage:
    """Clean Timescale storage for per-test isolation."""
    truncate_timescale_database(db_engine)
    return TimescaleStorage(engine=db_engine)


@pytest.fixture(scope="module")
def database_service_base_url(
    shared_storage: TimescaleStorage,
) -> Generator[str, None, None]:
    """Start the database service and return its base URL."""
    app = create_app(config=Config, storage=shared_storage)
    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield base_url
    finally:
        server.shutdown()
        thread.join()


@pytest.fixture
def database_api_client(database_service_base_url: str) -> DatabaseApiClient:
    """Create a database API client pointed at the test database service."""
    return DatabaseApiClient(base_url=database_service_base_url)
