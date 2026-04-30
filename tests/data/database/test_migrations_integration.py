"""Integration tests for executing migrations against TimescaleDB."""

import tempfile
import uuid
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import text
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


def test_run_migrations_supports_non_transactional_sql(
    postgres_container: PostgresContainer,
) -> None:
    """Apply migrations that must run outside a transaction block.

    Parameters
    ----------
    postgres_container : PostgresContainer
        Running TimescaleDB container.

    Returns
    -------
    None
        The assertions raise if non-transactional migrations are not supported.
    """
    db_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg://", "postgresql://"
    )
    run_id = uuid.uuid4().hex[:8]

    with tempfile.TemporaryDirectory() as tmp_dir:
        migrations_dir = Path(tmp_dir)

        first = migrations_dir / f"001_{run_id}_create_table.sql"
        second = migrations_dir / f"002_{run_id}_vacuum.sql"

        first.write_text(
            "CREATE TABLE IF NOT EXISTS vacuum_target (id SERIAL PRIMARY KEY);"
        )
        second.write_text(
            """
            -- migrate: no-transaction
            VACUUM vacuum_target;
            """
        )

        runner = MigrationRunner(migrations_dir=migrations_dir, db_url=db_url)
        runner.run_migrations()

        assert runner.get_pending_migrations() == []


def test_migration_004_creates_analytics_output_tables_and_indexes(
    db_engine,
) -> None:
    """Verify the analytics persistence schema is present after migrations."""
    with db_engine.connect() as conn:
        tables = {
            row.table_name
            for row in conn.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN (
                          'analytics_health_assessments',
                          'analytics_forecast_results',
                          'recommendation_lifecycle'
                      )
                    """
                )
            )
        }

        assert tables == {
            "analytics_health_assessments",
            "analytics_forecast_results",
            "recommendation_lifecycle",
        }

        health_columns = {
            row.column_name: row.data_type
            for row in conn.execute(
                text(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'analytics_health_assessments'
                    """
                )
            )
        }
        forecast_columns = {
            row.column_name: row.data_type
            for row in conn.execute(
                text(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'analytics_forecast_results'
                    """
                )
            )
        }
        lifecycle_columns = {
            row.column_name: row.data_type
            for row in conn.execute(
                text(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'recommendation_lifecycle'
                    """
                )
            )
        }

        assert health_columns["plant_id"] == "integer"
        assert health_columns["correlation_id"] == "character varying"
        assert health_columns["assessed_at"] == "timestamp with time zone"
        assert health_columns["score"] == "double precision"
        assert health_columns["confidence"] == "double precision"
        assert health_columns["model_metadata"] == "jsonb"

        assert forecast_columns["plant_id"] == "integer"
        assert forecast_columns["correlation_id"] == "character varying"
        assert forecast_columns["forecast_at"] == "timestamp with time zone"
        assert forecast_columns["horizon_seconds"] == "integer"
        assert forecast_columns["predicted_value"] == "double precision"
        assert forecast_columns["features_used"] == "jsonb"
        assert forecast_columns["inference_metadata"] == "jsonb"
        assert forecast_columns["model_metadata"] == "jsonb"

        assert lifecycle_columns["plant_id"] == "integer"
        assert lifecycle_columns["correlation_id"] == "character varying"
        assert lifecycle_columns["recommended_at"] == "timestamp with time zone"
        assert lifecycle_columns["actions"] == "jsonb"
        assert lifecycle_columns["recommendation_confidence"] == "double precision"
        assert lifecycle_columns["recommendation_reason"] == "text"
        assert lifecycle_columns["recommendation_model_metadata"] == "jsonb"
        assert lifecycle_columns["action_results"] == "jsonb"
        assert lifecycle_columns["decided_at"] == "timestamp with time zone"
        assert "recommendation" not in lifecycle_columns
        assert "controller_status" not in lifecycle_columns
        assert "controller_reason" not in lifecycle_columns
        assert "controller_mode" not in lifecycle_columns
        assert "action_id" not in lifecycle_columns

        health_indexes = {
            row.indexname
            for row in conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'analytics_health_assessments'")
            )
        }
        forecast_indexes = {
            row.indexname
            for row in conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'analytics_forecast_results'")
            )
        }
        lifecycle_indexes = {
            row.indexname
            for row in conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'recommendation_lifecycle'")
            )
        }

        assert "idx_analytics_health_assessments_plant_assessed_at" in health_indexes
        assert "idx_analytics_health_assessments_correlation_id" in health_indexes
        assert "idx_analytics_forecast_results_plant_forecast_at" in forecast_indexes
        assert "idx_analytics_forecast_results_correlation_id" in forecast_indexes
        assert "idx_recommendation_lifecycle_plant_recommended_at" in lifecycle_indexes
        assert "idx_recommendation_lifecycle_correlation_id" in lifecycle_indexes

        unique_constraints = {
            row.constraint_name
            for row in conn.execute(
                text(
                    """
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_name = 'recommendation_lifecycle'
                      AND constraint_type = 'UNIQUE'
                    """
                )
            )
        }

        assert "uq_recommendation_lifecycle_plant_correlation" in unique_constraints


def test_migration_004_defines_action_based_recommendation_lifecycle_schema(
    postgres_container: PostgresContainer,
) -> None:
    """Create the lifecycle table directly in its action-based shape."""
    db_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg://", "postgresql://"
    )
    server_url = db_url.rsplit("/", 1)[0] + "/postgres"
    run_db_name = f"analytics_schema_{uuid.uuid4().hex[:8]}"
    run_db_url = db_url.rsplit("/", 1)[0] + f"/{run_db_name}"

    with psycopg.connect(server_url, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{run_db_name}"')

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            migrations_dir = Path(tmp_dir)
            base_schema = migrations_dir / "001_create_plants_table.sql"
            migration_004 = migrations_dir / "002_add_analytics_output_tables.sql"

            base_schema.write_text(
                """
                CREATE TABLE IF NOT EXISTS plants (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL
                );
                """
            )
            migration_004.write_text(
                (
                    Path(__file__).resolve().parents[3]
                    / "dt/data/database/migrations/004_add_analytics_output_tables.sql"
                ).read_text()
            )

            runner = MigrationRunner(migrations_dir=migrations_dir, db_url=run_db_url)
            runner.run_migrations()

            with psycopg.connect(run_db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'recommendation_lifecycle'"
                    )
                    lifecycle_columns = {row[0]: row[1] for row in cur.fetchall()}

            assert lifecycle_columns["actions"] == "jsonb"
            assert lifecycle_columns["action_results"] == "jsonb"
            assert "recommendation" not in lifecycle_columns
            assert "controller_status" not in lifecycle_columns
            assert "controller_reason" not in lifecycle_columns
            assert "controller_mode" not in lifecycle_columns
            assert "action_id" not in lifecycle_columns
    finally:
        with psycopg.connect(server_url, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{run_db_name}"')
