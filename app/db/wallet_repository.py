# FILE: app/db/wallet_repository.py
# VERSION: 1.0.0

import logging
from typing import Dict, List, Set, Tuple

from app.db.database import Database


class WalletRepository:
    """
    Stores character wallet market transactions (1 year retention).
    """

    def __init__(self, db: Database):
        self.db = db
        self.logger = logging.getLogger("app.db.wallet_repository")

    def known_ids(self, transaction_ids: List[int]) -> Set[int]:
        if not transaction_ids:
            return set()

        placeholders = ",".join("?" for _ in transaction_ids)
        rows = self.db.query(
            f"""
            SELECT transaction_id FROM wallet_transactions
            WHERE transaction_id IN ({placeholders})
            """,
            tuple(transaction_ids),
        )
        return {row["transaction_id"] for row in rows}

    def upsert_transactions(
        self, character_id: int, rows: List[Dict]
    ) -> int:
        if not rows:
            return 0

        self.db.executemany(
            """
            INSERT OR IGNORE INTO wallet_transactions (
                transaction_id, character_id, date, type_id,
                quantity, unit_price, is_buy, location_id, client_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r.get("transaction_id", 0),
                    character_id,
                    r.get("date", ""),
                    r.get("type_id", 0),
                    r.get("quantity", 0),
                    float(r.get("unit_price", 0)),
                    int(bool(r.get("is_buy", False))),
                    r.get("location_id", 0),
                    r.get("client_id", 0),
                )
                for r in rows
            ],
        )

        self.logger.debug(
            "Stored %s wallet transactions for char %s",
            len(rows),
            character_id,
        )
        return len(rows)

    def sums(
        self,
        character_id: int,
        type_id: int,
        is_buy: bool,
        since: str,
    ) -> Tuple[int, float]:
        """
        Returns (total_quantity, total_isk) for a char/type since a date.
        """
        row = self.db.query_one(
            """
            SELECT COALESCE(SUM(quantity), 0) AS qty,
                   COALESCE(SUM(quantity * unit_price), 0) AS isk
            FROM wallet_transactions
            WHERE character_id = ? AND type_id = ?
              AND is_buy = ? AND date >= ?
            """,
            (character_id, type_id, int(is_buy), since),
        )

        if row is None:
            return 0, 0.0

        return int(row["qty"]), float(row["isk"])

    def purge_old(self, keep_days: int = 365) -> int:
        """
        Enforce the 1 year retention policy.
        """
        cursor = self.db.execute(
            """
            DELETE FROM wallet_transactions
            WHERE date < strftime('%Y-%m-%dT%H:%M:%S', 'now', ?)
            """,
            (f"-{keep_days} days",),
        )
        removed = cursor.rowcount

        if removed:
            self.logger.info(
                "Purged %s wallet transactions older than %s days",
                removed,
                keep_days,
            )

        return removed

    def count(self, character_id: int) -> int:
        row = self.db.query_one(
            "SELECT COUNT(*) AS cnt FROM wallet_transactions WHERE character_id = ?",
            (character_id,),
        )
        return int(row["cnt"]) if row else 0