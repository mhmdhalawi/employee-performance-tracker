from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from threading import Lock

from app.core.config import get_settings


_MIGRATIONS_DIRECTORY = Path(__file__).resolve().parents[2] / "migrations"
_initialization_lock = Lock()
_initialized_paths: set[Path] = set()


def database_path() -> Path:
    """Return the configured SQLite path as an absolute filesystem path."""
    return get_settings().database_path.expanduser().resolve()


def initialize_database(path: Path | None = None) -> Path:
    """Create the SQLite file and apply any unapplied numbered migrations."""
    resolved_path = (path or database_path()).expanduser().resolve()
    with _initialization_lock:
        if resolved_path in _initialized_paths:
            return resolved_path

        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(resolved_path, timeout=5)
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            current_version = connection.execute("PRAGMA user_version").fetchone()[0]
            for migration_path in sorted(_MIGRATIONS_DIRECTORY.glob("[0-9][0-9][0-9]_*.sql")):
                version = int(migration_path.name.split("_", 1)[0])
                if version <= current_version:
                    continue
                connection.executescript(migration_path.read_text(encoding="utf-8"))
                connection.execute(f"PRAGMA user_version = {version}")
                current_version = version
            connection.commit()
        finally:
            connection.close()

        _initialized_paths.add(resolved_path)
    return resolved_path


@contextmanager
def database_connection() -> Iterator[sqlite3.Connection]:
    """Open a short-lived configured SQLite connection with transaction handling."""
    path = initialize_database()
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
