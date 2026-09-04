# FILE: app/db/universe_cache_repository.py
# VERSION: 1.2.0

import logging
from typing import Dict, List, Optional

from app.db.database import Database


class UniverseCacheRepository:
    """
    Caches EVE universe names (systems, stations, types, structures)
    so we don't repeatedly hit ESI for the same IDs.
    """

    def __init__(self, db: Database):
        self.db = db
        self.logger = logging.getLogger("app.db.universe_cache")

    def get_name(self, eve_id: int) -> Optional[str]:
        row = self.db.query_one(
            "SELECT name FROM universe_cache WHERE eve_id = ?",
            (eve_id,),
        )
        if row is None:
            return None
        return row["name"]

    def get_name_by_category(self, eve_id: int, category: str) -> Optional[str]:
        row = self.db.query_one(
            """
            SELECT name FROM universe_cache
            WHERE eve_id = ? AND category = ?
            """,
            (eve_id, category),
        )
        if row is None:
            return None
        return row["name"]

    def get_names_by_category(
        self, eve_ids: List[int], category: str
    ) -> Dict[int, str]:
        """
        Chunked bulk lookup: one IN(...) query per 500 ids instead of
        one query per id.
        """
        out: Dict[int, str] = {}
        for start in range(0, len(eve_ids), 500):
            chunk = eve_ids[start:start + 500]
            placeholders = ",".join("?" for _ in chunk)
            rows = self.db.query(
                f"SELECT eve_id, name FROM universe_cache "
                f"WHERE category = ? AND eve_id IN ({placeholders})",
                (category, *chunk),
            )
            for row in rows:
                out[row["eve_id"]] = row["name"]
        return out

    def get_names(self, eve_ids: List[int]) -> Dict[int, str]:
        if not eve_ids:
            return {}
        placeholders = ",".join("?" for _ in eve_ids)
        rows = self.db.query(
            f"SELECT eve_id, name FROM universe_cache WHERE eve_id IN ({placeholders})",
            tuple(eve_ids),
        )
        return {row["eve_id"]: row["name"] for row in rows}

    def set_name(self, eve_id: int, name: str, category: str = "unknown") -> None:
        self.db.execute(
            """
            INSERT INTO universe_cache (eve_id, name, category)
            VALUES (?, ?, ?)
            ON CONFLICT(eve_id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                fetched_at=CURRENT_TIMESTAMP
            """,
            (eve_id, name, category),
        )

    def set_names(self, entries: Dict[int, str], category: str = "unknown") -> None:
        for eve_id, name in entries.items():
            self.set_name(eve_id, name, category)

    def count(self) -> int:
        row = self.db.query_one("SELECT COUNT(*) AS cnt FROM universe_cache")
        return row["cnt"] if row else 0