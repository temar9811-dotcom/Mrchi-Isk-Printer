# FILE: app/db/esi_cache_repository.py
# VERSION: 1.0.0

import json
import logging
import time
from typing import Any, Optional, Tuple

from app.db.database import Database


class EsiCacheRepository:
    """
    Generic JSON payload cache for ESI responses (PI layouts etc).
    """

    def __init__(self, db: Database):
        self.db = db
        self.logger = logging.getLogger("app.db.esi_cache")

    def get(self, key: str) -> Tuple[Optional[Any], Optional[float]]:
        row = self.db.query_one(
            "SELECT payload, fetched_at FROM esi_cache WHERE cache_key = ?",
            (key,),
        )
        if row is None:
            return None, None
        try:
            return json.loads(row["payload"]), float(row["fetched_at"])
        except Exception:
            self.logger.warning("Bad esi_cache payload for %s", key)
            return None, None

    def set(self, key: str, payload: Any) -> None:
        self.db.execute(
            """
            INSERT INTO esi_cache (cache_key, payload, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                payload=excluded.payload,
                fetched_at=excluded.fetched_at
            """,
            (key, json.dumps(payload), time.time()),
        )

    def fetched_at(self, key: str) -> Optional[float]:
        row = self.db.query_one(
            "SELECT fetched_at FROM esi_cache WHERE cache_key = ?",
            (key,),
        )
        if row is None:
            return None
        return float(row["fetched_at"])

    def age(self, key: str) -> Optional[float]:
        fetched = self.fetched_at(key)
        if fetched is None:
            return None
        return time.time() - fetched