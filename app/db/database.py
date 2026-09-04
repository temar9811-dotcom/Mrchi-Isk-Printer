# FILE: app/db/database.py
# VERSION: 1.4.0

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from app.db.schema import SCHEMA_STATEMENTS, apply_migrations


class Database:
    """
    Small SQLite wrapper.
    """

    def __init__(self, db_path: Union[Path, str]):
        self.db_path = Path(db_path)
        self.logger = logging.getLogger("app.db")
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        with self._lock:
            if self._conn is not None:
                return
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.logger.debug(
                "Connecting to SQLite database: %s",
                self.db_path.resolve(),
            )
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self.logger.info("SQLite connection established")

    def close(self) -> None:
        with self._lock:
            if self._conn is None:
                return
            self.logger.debug("Closing SQLite database")
            self._conn.close()
            self._conn = None

    def _ensure_connection(self) -> None:
        if self._conn is None:
            self.connect()

    def _log_sql(self, label: str, sql: str, params: Tuple[Any, ...]) -> None:
        one_line = " ".join(sql.strip().split())
        if len(one_line) > 220:
            one_line = one_line[:217] + "..."
        self.logger.debug("%s SQL: %s | params=%s", label, one_line, params)

    def execute(
        self, sql: str, params: Tuple[Any, ...] = (),
    ) -> sqlite3.Cursor:
        with self._lock:
            self._ensure_connection()
            self._log_sql("EXECUTE", sql, params)
            cursor = self._conn.execute(sql, params)
            self._conn.commit()
            return cursor

    def executemany(
        self, sql: str, params_list: List[Tuple[Any, ...]],
    ) -> sqlite3.Cursor:
        with self._lock:
            self._ensure_connection()
            self._log_sql(
                "EXECUTEMANY", sql, (f"{len(params_list)} row(s)",)
            )
            cursor = self._conn.executemany(sql, params_list)
            self._conn.commit()
            return cursor

    def query(
        self, sql: str, params: Tuple[Any, ...] = (),
    ) -> List[sqlite3.Row]:
        with self._lock:
            self._ensure_connection()
            self._log_sql("QUERY", sql, params)
            cursor = self._conn.execute(sql, params)
            return cursor.fetchall()

    def query_one(
        self, sql: str, params: Tuple[Any, ...] = (),
    ) -> Optional[sqlite3.Row]:
        rows = self.query(sql, params)
        if not rows:
            return None
        return rows[0]

    def log_debug_event(self, event_type: str, message: str) -> None:
        self.execute(
            "INSERT INTO debug_events (event_type, message) VALUES (?, ?)",
            (event_type, message),
        )

    def init_schema(self) -> None:
        self.logger.info("Initializing database schema")
        for statement in SCHEMA_STATEMENTS:
            self.execute(statement)
        apply_migrations(self)
        self.log_debug_event("schema", "Database schema initialized")
        self.logger.info("Database schema initialized")