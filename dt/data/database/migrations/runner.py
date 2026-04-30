"""SQL migration runner for PostgreSQL/TimescaleDB."""

import logging
from dataclasses import dataclass
from pathlib import Path

import psycopg

logger = logging.getLogger(__name__)


@dataclass
class Migration:
    """Represents a single SQL migration file."""

    name: str
    path: Path

    def read_sql(self) -> str:
        """Read the SQL content from the migration file."""
        return self.path.read_text()


class MigrationRunner:
    """Runs SQL migrations against a PostgreSQL database."""

    MIGRATIONS_TABLE = "schema_migrations"
    NO_TRANSACTION_MARKER = "-- migrate: no-transaction"

    def __init__(self, migrations_dir: Path | str, db_url: str | None = None):
        """Initialize the migration runner.

        Parameters
        ----------
        migrations_dir : Path | str
            Directory containing SQL migration files
        db_url : str | None
            PostgreSQL connection URL. If None, only discovery methods work.
        """
        self.migrations_dir = Path(migrations_dir)
        self.db_url = db_url

    def get_pending_migrations(self) -> list[Migration]:
        """Get all pending migration files sorted by name.

        Returns
        -------
        list[Migration]
            List of migration files that haven't been applied yet
        """
        all_migrations = self._discover_migrations()

        if self.db_url is None:
            return all_migrations

        applied = self._get_applied_migrations()

        return [m for m in all_migrations if m.name not in applied]

    def _discover_migrations(self) -> list[Migration]:
        """Discover all SQL migration files in the migrations directory.

        Returns
        -------
        list[Migration]
            List of all migration files sorted by name
        """
        if not self.migrations_dir.exists():
            return []

        sql_files = sorted(self.migrations_dir.glob("*.sql"))
        return [Migration(name=f.name, path=f) for f in sql_files]

    def _get_applied_migrations(self) -> set[str]:
        """Get the set of migration names that have already been applied.

        Returns
        -------
        set[str]
            Set of migration file names that have been applied
        """
        if self.db_url is None:
            return set()

        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                # Create migrations tracking table if it doesn't exist
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.MIGRATIONS_TABLE} (
                        id SERIAL PRIMARY KEY,
                        migration_name VARCHAR(255) NOT NULL UNIQUE,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """)
                conn.commit()

                # Get all applied migrations
                cur.execute(f"SELECT migration_name FROM {self.MIGRATIONS_TABLE};")
                return {row[0] for row in cur.fetchall()}

    def run_migrations(self) -> None:
        """Execute all pending migrations against the database."""
        if self.db_url is None:
            raise ValueError("Cannot run migrations without a database URL")

        pending = self.get_pending_migrations()

        if not pending:
            logger.info("No pending migrations to apply")
            return

        logger.info(f"Found {len(pending)} pending migration(s)")

        for migration in pending:
            logger.info(f"Applying migration: {migration.name}")
            sql = migration.read_sql()
            autocommit = self._requires_autocommit(sql)
            statements = self._split_statements(sql) if autocommit else [sql]

            with psycopg.connect(self.db_url, autocommit=autocommit) as conn:
                with conn.cursor() as cur:
                    for statement in statements:
                        cur.execute(statement)
                    cur.execute(
                        f"""
                        INSERT INTO {self.MIGRATIONS_TABLE} (migration_name)
                        VALUES (%s);
                        """,
                        (migration.name,),
                    )

                if not autocommit:
                    conn.commit()

            logger.info(f"Successfully applied migration: {migration.name}")

        logger.info("All migrations applied successfully")

    @classmethod
    def _requires_autocommit(cls, sql: str) -> bool:
        """Return whether a migration must run outside a transaction."""
        return cls.NO_TRANSACTION_MARKER in sql

    @staticmethod
    def _split_statements(sql: str) -> list[str]:
        """Split migration SQL into executable statements."""
        statements: list[str] = []
        for chunk in sql.split(";"):
            statement = chunk.strip()
            if statement:
                statements.append(f"{statement};")
        return statements
