# FILE: app/db/contract_repository.py
# VERSION: 1.0.0

import logging
import time
from typing import Dict, List, Optional

from app.db.database import Database


class ContractRepository:
    """
    SQLite persistence for ESI contracts + their items.
    """

    def __init__(self, db: Database):
        self.db = db
        self.logger = logging.getLogger("app.db.contract_repository")

    def upsert_contracts(self, character_id: int, contracts: List[Dict]) -> int:
        if not contracts:
            return 0
        now = time.time()
        self.db.executemany(
            """
            INSERT INTO contracts (
                contract_id, character_id, issuer_id, assignee_id, acceptor_id,
                start_location_id, end_location_id, title, contract_type, status,
                availability, date_issued, date_accepted, date_completed, date_expired,
                price, reward, collateral, buyout, volume, days_to_complete, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(contract_id) DO UPDATE SET
                character_id=excluded.character_id,
                status=excluded.status,
                acceptor_id=excluded.acceptor_id,
                assignee_id=excluded.assignee_id,
                date_accepted=excluded.date_accepted,
                date_completed=excluded.date_completed,
                date_expired=excluded.date_expired,
                fetched_at=excluded.fetched_at
            """,
            [
                (
                    int(c.get("contract_id", 0)),
                    character_id,
                    c.get("issuer_id"),
                    c.get("assignee_id"),
                    c.get("acceptor_id"),
                    c.get("start_location_id"),
                    c.get("end_location_id"),
                    c.get("title") or "",
                    c.get("type") or "unknown",
                    c.get("status") or "unknown",
                    c.get("availability"),
                    c.get("date_issued") or "",
                    c.get("date_accepted") or "",
                    c.get("date_completed") or "",
                    c.get("date_expired") or "",
                    float(c.get("price", 0) or 0),
                    float(c.get("reward", 0) or 0),
                    float(c.get("collateral", 0) or 0),
                    float(c.get("buyout", 0) or 0),
                    float(c.get("volume", 0) or 0),
                    c.get("days_to_complete"),
                    now,
                )
                for c in contracts
            ],
        )
        self.logger.debug("Upserted %s contracts for char %s", len(contracts), character_id)
        return len(contracts)

    def get_contracts(
        self,
        character_id: Optional[int] = None,
        contract_type: Optional[str] = None,
    ) -> List[Dict]:
        sql = "SELECT * FROM contracts WHERE 1=1"
        params: List = []
        if character_id is not None:
            sql += " AND character_id = ?"
            params.append(character_id)
        if contract_type is not None:
            sql += " AND contract_type = ?"
            params.append(contract_type)
        sql += " ORDER BY date_issued DESC"
        return [dict(row) for row in self.db.query(sql, tuple(params))]

    def upsert_items(self, contract_id: int, items: List[Dict]) -> int:
        if not items:
            return 0
        self.db.executemany(
            """
            INSERT INTO contract_items (
                contract_id, record_id, type_id, quantity, is_included, is_singleton
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(contract_id, record_id) DO UPDATE SET
                quantity=excluded.quantity,
                is_included=excluded.is_included
            """,
            [
                (
                    contract_id,
                    int(i.get("record_id", 0)),
                    int(i.get("type_id", 0)),
                    int(i.get("quantity", 0)),
                    1 if i.get("is_included", True) else 0,
                    1 if i.get("is_singleton", False) else 0,
                )
                for i in items
            ],
        )
        return len(items)

    def get_items(self, contract_id: int) -> List[Dict]:
        rows = self.db.query(
            "SELECT * FROM contract_items WHERE contract_id = ?",
            (contract_id,),
        )
        return [dict(row) for row in rows]

    def count(self, character_id: Optional[int] = None) -> int:
        if character_id is None:
            row = self.db.query_one("SELECT COUNT(*) AS cnt FROM contracts")
        else:
            row = self.db.query_one(
                "SELECT COUNT(*) AS cnt FROM contracts WHERE character_id = ?",
                (character_id,),
            )
        return int(row["cnt"]) if row else 0