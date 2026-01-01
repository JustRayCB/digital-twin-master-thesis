"""Integration tests for executing migrations against TimescaleDB."""

import tempfile
import uuid
from pathlib import Path

import psycopg
import pytest
from testcontainers.postgres import PostgresContainer

from dt.data.database.migrations.runner import MigrationRunner

pytestmark = [pytest.mark.requires_timescale]


def test_run_migrations_executes_sql_against_database(
    postgres_container: PostgresContainer,
) -> None:
    """Apply SQL migrations to a real database.

    Parameters
    ----------
    postgres_container : PostgresContainer
        Running TimescaleDB container.

    Returns
    -------
    None
        The assertions raise if migrations fail to execute.
    """
    db_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg://", "postgresql://"
    )
    run_id = uuid.uuid4().hex[:8]

    with tempfile.TemporaryDirectory() as tmp_dir:
        migrations_dir = Path(tmp_dir)
        migration_file = migrations_dir / f"001_{run_id}_create_table.sql"
        migration_file.write_text(
            """
            CREATE TABLE IF NOT EXISTS test_plants (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL
            );
            INSERT INTO test_plants (name) VALUES ('Test Plant 1');
            """
        )

        runner = MigrationRunner(migrations_dir=migrations_dir, db_url=db_url)
        runner.run_migrations()

        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM test_plants;")
                assert cur.fetchone()[0] == 1


def test_get_pending_migrations_excludes_applied_migrations(
    postgres_container: PostgresContainer,
) -> None:
    """Track applied migrations via schema_migrations table.

    Parameters
    ----------
    postgres_container : PostgresContainer
        Running TimescaleDB container.

    Returns
    -------
    None
        The assertions raise if applied migrations are not tracked correctly.
    """
    db_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg://", "postgresql://"
    )
    run_id = uuid.uuid4().hex[:8]

    with tempfile.TemporaryDirectory() as tmp_dir:
        migrations_dir = Path(tmp_dir)

        first = migrations_dir / f"001_{run_id}_first.sql"
        second = migrations_dir / f"002_{run_id}_second.sql"

        first.write_text("CREATE TABLE IF NOT EXISTS first_table (id SERIAL PRIMARY KEY);")
        runner = MigrationRunner(migrations_dir=migrations_dir, db_url=db_url)
        runner.run_migrations()

        second.write_text("CREATE TABLE IF NOT EXISTS second_table (id SERIAL PRIMARY KEY);")
        runner = MigrationRunner(migrations_dir=migrations_dir, db_url=db_url)
        pending = runner.get_pending_migrations()

        assert [migration.name for migration in pending] == [second.name]
