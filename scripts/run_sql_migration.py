#!/usr/bin/env python3
"""CLI script to run SQL migrations against PostgreSQL/TimescaleDB.

Usage:
    python scripts/run_sql_migration.py

Environment variables:
    PG_DATABASE_URL: PostgreSQL connection string
                     (default: postgresql+psycopg://dt:dt@localhost:5432/dt)
"""

import logging
import sys
from pathlib import Path

from dt.data.database.migrations.runner import MigrationRunner
from dt.utils.config import Config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    """Run pending migrations."""

    # Get database URL from config
    db_url = Config.PG_DATABASE_URL
    if not db_url:
        logger.error("PG_DATABASE_URL not configured")
        logger.error("Please set the PG_DATABASE_URL environment variable")
        sys.exit(1)

    # Convert SQLAlchemy URL format to psycopg format if needed
    if "postgresql+psycopg" in db_url:
        db_url = db_url.replace("postgresql+psycopg", "postgresql")

    # Determine migrations directory
    repo_root = Path(__file__).parent.parent
    migrations_dir = repo_root / "dt" / "data" / "database" / "migrations"

    if not migrations_dir.exists():
        logger.error(f"Migrations directory not found: {migrations_dir}")
        sys.exit(1)

    logger.info(f"Running migrations from: {migrations_dir}")
    logger.info(f"Database URL: {db_url.split('@')[1] if '@' in db_url else 'local'}")

    try:
        runner = MigrationRunner(migrations_dir=migrations_dir, db_url=db_url)
        runner.run_migrations()
        logger.info("Migration process completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
