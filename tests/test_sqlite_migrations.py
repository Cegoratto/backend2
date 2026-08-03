from pathlib import Path

from app.db.sqlite_migrations import migrate_users_password_hash_nullable


def test_migrate_users_password_hash_nullable_updates_existing_sqlite_db(tmp_path):
    db_path = tmp_path / "kanban.db"
    conn = __import__("sqlite3").connect(db_path)
    conn.execute(
        """
        CREATE TABLE users (
            id TEXT NOT NULL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            team_role VARCHAR(100),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO users (id, email, password_hash, name) VALUES (?, ?, ?, ?)",
        ("user-1", "alice@example.com", "hash", "Alice"),
    )
    conn.commit()
    conn.close()

    migrate_users_password_hash_nullable(f"sqlite+aiosqlite:///{db_path.as_posix()}")

    conn = __import__("sqlite3").connect(db_path)
    columns = conn.execute("PRAGMA table_info(users)").fetchall()
    password_hash_column = next(column for column in columns if column[1] == "password_hash")
    rows = conn.execute("SELECT email, password_hash FROM users").fetchall()
    conn.close()

    assert password_hash_column[3] == 0
    assert rows == [("alice@example.com", "hash")]


def test_migrate_users_password_hash_nullable_is_idempotent(tmp_path):
    db_path = tmp_path / "kanban.db"
    conn = __import__("sqlite3").connect(db_path)
    conn.execute(
        """
        CREATE TABLE users (
            id TEXT NOT NULL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            password_hash VARCHAR(255),
            name VARCHAR(255) NOT NULL,
            team_role VARCHAR(100),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    database_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    migrate_users_password_hash_nullable(database_url)
    migrate_users_password_hash_nullable(database_url)

    conn = __import__("sqlite3").connect(db_path)
    columns = conn.execute("PRAGMA table_info(users)").fetchall()
    conn.close()

    password_hash_column = next(column for column in columns if column[1] == "password_hash")
    assert password_hash_column[3] == 0
