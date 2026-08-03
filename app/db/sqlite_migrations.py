import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlparse


def _sqlite_path_from_url(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite"):
        return None

    parsed = urlparse(database_url)
    if parsed.path == "/:memory:":
        return None

    raw_path = unquote(parsed.path.lstrip("/"))
    if len(parsed.path) > 1 and parsed.path.startswith("/") and raw_path.startswith("/"):
        raw_path = unquote(parsed.path)

    path = Path(raw_path)
    if not path.is_absolute() and database_url.startswith("sqlite+aiosqlite:///./"):
        relative = database_url.split("sqlite+aiosqlite:///./", 1)[1]
        path = Path(unquote(relative))

    return path


def _password_hash_is_not_null(conn: sqlite3.Connection) -> bool:
    columns = conn.execute("PRAGMA table_info(users)").fetchall()
    for column in columns:
        if column[1] == "password_hash":
            return bool(column[3])
    return False


def migrate_users_password_hash_nullable(database_url: str) -> None:
    db_path = _sqlite_path_from_url(database_url)
    if db_path is None or not db_path.exists():
        return

    conn = sqlite3.connect(db_path)
    try:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        if not table_exists or not _password_hash_is_not_null(conn):
            return

        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            """
            CREATE TABLE users_new (
                id UUID NOT NULL PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255),
                name VARCHAR(255) NOT NULL,
                team_role VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """
        )
        conn.execute("INSERT INTO users_new SELECT * FROM users")
        conn.execute("DROP TABLE users")
        conn.execute("ALTER TABLE users_new RENAME TO users")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")
        conn.commit()
    finally:
        conn.close()
