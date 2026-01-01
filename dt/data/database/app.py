"""Flask application for the database service.

This application serves as the main entry point for the database service.
It performs two primary functions:

1.  Messaging Bridge: It sets up a Kafka client that subscribes to various
    sensor data topics. When a message is received, it is forwarded to the
    configured storage backend (e.g., TimescaleDB) for persistence.

2.  REST API: It exposes a set of HTTP endpoints for interacting with the
    database. This includes endpoints for binding new sensors and querying
    historical sensor data by time range or sensor ID.
"""

from flask import Flask
from flask_cors import CORS

from dt.data.database.api import create_database_blueprint
from dt.data.database.consumer import setup_bridge
from dt.data.database.migrations.runner import MigrationRunner
from dt.data.database.storage import Storage
from dt.utils import Config, get_logger

logger = get_logger(__name__)


def run_startup_migrations(db_url: str, migrations_dir: str) -> None:
    """Run SQL migrations required by the database service.

    Parameters
    ----------
    db_url : str
        PostgreSQL connection URL (SQLAlchemy-style URLs are accepted).
    migrations_dir : Path | str | None
        Directory containing SQL migration files. Defaults to the repo migrations directory.
    """
    if not db_url:
        raise ValueError("PG_DATABASE_URL not configured")

    if "postgresql+psycopg" in db_url:
        db_url = db_url.replace("postgresql+psycopg", "postgresql")

    runner = MigrationRunner(migrations_dir=migrations_dir, db_url=db_url)
    runner.run_migrations()


def create_app(config, storage: Storage) -> Flask:
    """Create and configure the Flask application with dependency-injected storage.

    This factory function creates a Flask app instance, registers the database
    blueprint, and wires the provided storage backend.

    Parameters
    ----------
    config : Config
        Configuration object containing application settings.
    storage : Storage
        Storage backend instance.

    Returns
    -------
    Flask
        Configured Flask application instance.
    """
    if storage is None:
        raise ValueError("Storage instance is required")

    app = Flask(__name__)
    CORS(app)

    # Store config and storage in app context
    app.config["STORAGE"] = storage
    app.config["DT_CONFIG"] = config

    logger.info(f"Creating Flask app with storage: {type(storage).__name__}")

    # Register Blueprint
    db_bp = create_database_blueprint(storage)
    app.register_blueprint(db_bp)

    return app


if __name__ == "__main__":
    import os

    from dt.data.database import TimescaleStorage
    from dt.utils import Config

    # Ensure the setup runs only once, not in the reloader process
    in_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    debug_mode = True

    # Ensure schema is initialized before starting the service
    if debug_mode and in_reloader:
        run_startup_migrations(
            db_url=Config.PG_DATABASE_URL, migrations_dir=Config.DB_MIGRATIONS_DIR
        )
    elif not debug_mode:
        run_startup_migrations(
            db_url=Config.PG_DATABASE_URL, migrations_dir=Config.DB_MIGRATIONS_DIR
        )

    # Initialize storage backend (TimescaleDB)
    storage = TimescaleStorage()

    # Create Flask app using factory
    app = create_app(config=Config, storage=storage)

    # Setup Kafka bridge
    msg_client = None
    if debug_mode and in_reloader:
        msg_client = setup_bridge(config=Config, storage=storage)
    elif not debug_mode:
        msg_client = setup_bridge(config=Config, storage=storage)

    app.run(host="0.0.0.0", port=5001, debug=debug_mode)