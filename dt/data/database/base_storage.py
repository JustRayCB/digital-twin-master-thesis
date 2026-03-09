from abc import ABC
from contextlib import contextmanager
from typing import Any, Generator, Optional

from sqlalchemy import Connection, Engine, create_engine

from dt.utils import Config, get_logger


def create_database_engine(
    database_url: str = Config.PG_DATABASE_URL,
    pool_size: int = int(Config.SQL_POOL_SIZE),
) -> Engine:
    """Create a shared SQLAlchemy engine for database stores."""
    return create_engine(database_url, pool_size=pool_size, pool_pre_ping=True)


class DatabaseStorage(ABC):
    """Shared database infrastructure for storage repositories."""

    def __init__(
        self,
        engine: Optional[Engine] = None,
        database_url: str = Config.PG_DATABASE_URL,
        pool_size: int = int(Config.SQL_POOL_SIZE),
    ) -> None:
        self.logger = get_logger(type(self).__module__)
        if engine:
            self.engine = engine
            self.logger.info("Using provided SQLAlchemy engine")
        else:
            self.engine = create_database_engine(database_url=database_url, pool_size=pool_size)
            self.logger.info(
                f"Created SQLAlchemy engine with pool size {int(pool_size or Config.SQL_POOL_SIZE)}"
            )

    @contextmanager
    def _get_connection(self) -> Generator[Connection, None, None]:
        """Provide a transactional database connection."""
        conn = self.engine.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _get_id(self, result: Any) -> int:
        """Extract newly created ID from a RETURNING clause result."""
        new_id = result.scalar()
        if new_id is None or not str(new_id).isdigit():
            raise RuntimeError("Failed to retrieve ID from database operation")
        return int(new_id)

    def close(self) -> None:
        """Close any open connections"""
        if self.engine:
            self.engine.dispose()
            self.logger.info(f"{type(self).__name__} engine disposed")
