import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    user_id: int
    username: str | None
    is_active: bool
    is_admin: bool
    created_at: str


@dataclass
class ProxyKey:
    key_id: int
    user_id: int
    secret: str
    connection_uri: str
    created_at: str


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS proxy_keys (
                    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    secret TEXT NOT NULL,
                    connection_uri TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
                """
            )

    def upsert_user(self, user_id: int, username: str | None, is_admin: bool) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, username, is_active, is_admin, created_at)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    is_admin = excluded.is_admin
                """,
                (user_id, username, int(is_admin), now),
            )

    def set_user_status(self, user_id: int, is_active: bool) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE users SET is_active = ? WHERE user_id = ?",
                (int(is_active), user_id),
            )
            return cur.rowcount > 0

    def is_active_user(self, user_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT is_active FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row is None:
                return False
            return bool(row["is_active"])

    def create_proxy_key(self, user_id: int, secret: str, connection_uri: str) -> ProxyKey:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO proxy_keys (user_id, secret, connection_uri, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, secret, connection_uri, now),
            )
            key_id = cur.lastrowid

        return ProxyKey(
            key_id=key_id,
            user_id=user_id,
            secret=secret,
            connection_uri=connection_uri,
            created_at=now,
        )

    def list_users(self) -> list[User]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT user_id, username, is_active, is_admin, created_at FROM users ORDER BY created_at DESC"
            ).fetchall()
        return [
            User(
                user_id=row["user_id"],
                username=row["username"],
                is_active=bool(row["is_active"]),
                is_admin=bool(row["is_admin"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]