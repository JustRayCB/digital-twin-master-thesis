"""Unit tests for SQL migration discovery."""

from pathlib import Path

from dt.data.database.migrations.runner import MigrationRunner


def test_get_pending_migrations_lists_sql_files_sorted(tmp_path: Path) -> None:
    """Discover SQL migrations in lexicographic order.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory used as the migrations root.

    Returns
    -------
    None
        The assertions raise if migration ordering regresses.
    """
    (tmp_path / "002_second.sql").write_text("-- second")
    (tmp_path / "001_first.sql").write_text("-- first")
    (tmp_path / "003_third.sql").write_text("-- third")

    runner = MigrationRunner(migrations_dir=tmp_path)
    migrations = runner.get_pending_migrations()

    assert [migration.name for migration in migrations] == [
        "001_first.sql",
        "002_second.sql",
        "003_third.sql",
    ]


def test_get_pending_migrations_ignores_non_sql_files(tmp_path: Path) -> None:
    """Ignore non-SQL files during migration discovery.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory used as the migrations root.

    Returns
    -------
    None
        The assertions raise if non-SQL filtering regresses.
    """
    (tmp_path / "001_migration.sql").write_text("-- migration")
    (tmp_path / "README.md").write_text("# not a migration")
    (tmp_path / "notes.txt").write_text("not a migration")

    runner = MigrationRunner(migrations_dir=tmp_path)
    migrations = runner.get_pending_migrations()

    assert [migration.name for migration in migrations] == ["001_migration.sql"]
