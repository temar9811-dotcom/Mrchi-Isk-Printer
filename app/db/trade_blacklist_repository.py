# FILE: app/db/trade_blacklist_repository.py
# VERSION: 1.0.0

import logging
from typing import Dict, List, Set

from app.db.database import Database


class TradeBlacklistRepository:
    """
    Items the user never wants the trade calculator to touch.
    """

    def __init__(self, db: Database):
        self.db = db
        self.logger = logging.getLogger("app.db.trade_blacklist")

    def get_ids(self) -> Set[int]:
        rows = self.db.query("SELECT type_id FROM trade_blacklist")
        return {row["type_id"] for row in rows}

    def get_all(self) -> List[Dict]:
        rows = self.db.query(
            "SELECT type_id, type_name, added_at FROM trade_blacklist "
            "ORDER BY type_name"
        )
        return [
            {
                "type_id": row["type_id"],
                "type_name": row["type_name"],
                "added_at": row["added_at"],
            }
            for row in rows
        ]

    def add(self, type_id: int, type_name: str) -> None:
        self.db.execute(
            """
            INSERT OR IGNORE INTO trade_blacklist (type_id, type_name)
            VALUES (?, ?)
            """,
            (type_id, type_name),
        )
        self.logger.info("Blacklisted %s (%s)", type_name, type_id)

    def remove(self, type_id: int) -> None:
        self.db.execute(
            "DELETE FROM trade_blacklist WHERE type_id = ?",
            (type_id,),
        )
        self.logger.info("Removed %s from blacklist", type_id)
        