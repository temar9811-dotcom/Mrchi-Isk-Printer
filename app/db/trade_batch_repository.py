# FILE: app/db/trade_batch_repository.py
# VERSION: 1.5.0

import logging
from typing import List, Optional, Set, Dict, Any

from app.db.database import Database
from app.models.trade_batch import TradeBatch, TradeBatchItem


class TradeBatchRepository:
    """
    Handles persistence for active and historical trade batches.
    """

    def __init__(self, db: Database):
        self.db = db
        self.logger = logging.getLogger("app.db.trade_batch_repository")

    def save_batch(self, batch: TradeBatch) -> int:
        cursor = self.db.execute(
            """
            INSERT INTO trade_batches (
                buy_char_id, sell_char_id, status, expected_profit, notes
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                batch.buy_char_id,
                batch.sell_char_id,
                batch.status,
                batch.expected_profit,
                batch.notes,
            ),
        )
        batch_id = cursor.lastrowid
        self.logger.info("Created new trade batch: %s", batch_id)

        for item in batch.items:
            self.db.execute(
                """
                INSERT INTO trade_batch_items (
                    batch_id, type_id, type_name, quantity, buy_price, sell_price
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    item.type_id,
                    item.type_name,
                    item.quantity,
                    item.buy_price,
                    item.sell_price,
                ),
            )
        return batch_id

    def get_active_type_ids(self) -> Set[int]:
        rows = self.db.query(
            """
            SELECT DISTINCT i.type_id
            FROM trade_batch_items i
            JOIN trade_batches b ON i.batch_id = b.batch_id
            WHERE b.status = 'active'
            """
        )
        return {row["type_id"] for row in rows}

    def get_active_batches(self) -> List[TradeBatch]:
        rows = self.db.query(
            """
            SELECT batch_id, buy_char_id, sell_char_id, status, created_at,
                   expected_profit, actual_profit, notes
            FROM trade_batches
            WHERE status = 'active'
            ORDER BY created_at DESC
            """
        )
        batches: List[TradeBatch] = []
        for row in rows:
            batch = TradeBatch(
                batch_id=row["batch_id"],
                buy_char_id=row["buy_char_id"] or 0,
                sell_char_id=row["sell_char_id"] or 0,
                status=row["status"],
                created_at=row["created_at"] or "",
                expected_profit=row["expected_profit"] or 0.0,
                actual_profit=row["actual_profit"] or 0.0,
                notes=row["notes"] or "",
            )
            item_rows = self.db.query(
                """
                SELECT item_id, batch_id, type_id, type_name, quantity,
                       buy_price, sell_price, status, bought_qty, sold_qty,
                       buy_spent, sell_received, sold_at, time_to_sell_days,
                       COALESCE(status_override, '') AS status_override
                FROM trade_batch_items
                WHERE batch_id = ?
                """,
                (batch.batch_id,),
            )
            for i_row in item_rows:
                batch.items.append(TradeBatchItem(
                    item_id=i_row["item_id"],
                    batch_id=batch.batch_id,
                    type_id=i_row["type_id"],
                    type_name=i_row["type_name"],
                    quantity=i_row["quantity"],
                    buy_price=i_row["buy_price"],
                    sell_price=i_row["sell_price"],
                    status=i_row["status"],
                    bought_qty=i_row["bought_qty"],
                    sold_qty=i_row["sold_qty"],
                    buy_spent=i_row["buy_spent"],
                    sell_received=i_row["sell_received"],
                    status_override=i_row["status_override"] or "",
                    sold_at=i_row["sold_at"] or "",
                    time_to_sell_days=i_row["time_to_sell_days"] or 0.0,
                ))
            batches.append(batch)
        return batches

    def get_completed_batches(self, limit: int = 50) -> List[TradeBatch]:
        rows = self.db.query(
            """
            SELECT batch_id, buy_char_id, sell_char_id, status, created_at,
                   completed_at, expected_profit, actual_profit, notes
            FROM trade_batches
            WHERE status = 'completed'
            ORDER BY completed_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        batches: List[TradeBatch] = []
        for row in rows:
            batch = TradeBatch(
                batch_id=row["batch_id"],
                buy_char_id=row["buy_char_id"] or 0,
                sell_char_id=row["sell_char_id"] or 0,
                status=row["status"],
                created_at=row["created_at"] or "",
                completed_at=row["completed_at"] or "",
                expected_profit=row["expected_profit"] or 0.0,
                actual_profit=row["actual_profit"] or 0.0,
                notes=row["notes"] or "",
            )
            item_rows = self.db.query(
                """
                SELECT item_id, batch_id, type_id, type_name, quantity,
                       buy_price, sell_price, status, bought_qty, sold_qty,
                       buy_spent, sell_received, sold_at, time_to_sell_days,
                       COALESCE(status_override, '') AS status_override
                FROM trade_batch_items
                WHERE batch_id = ?
                """,
                (batch.batch_id,),
            )
            for i_row in item_rows:
                batch.items.append(TradeBatchItem(
                    item_id=i_row["item_id"],
                    batch_id=batch.batch_id,
                    type_id=i_row["type_id"],
                    type_name=i_row["type_name"],
                    quantity=i_row["quantity"],
                    buy_price=i_row["buy_price"],
                    sell_price=i_row["sell_price"],
                    status=i_row["status"],
                    bought_qty=i_row["bought_qty"],
                    sold_qty=i_row["sold_qty"],
                    buy_spent=i_row["buy_spent"],
                    sell_received=i_row["sell_received"],
                    status_override=i_row["status_override"] or "",
                    sold_at=i_row["sold_at"] or "",
                    time_to_sell_days=i_row["time_to_sell_days"] or 0.0,
                ))
            batches.append(batch)
        return batches

    def get_pnl_summary(self) -> Dict[str, Any]:
        rows = self.db.query(
            """
            SELECT batch_id, expected_profit, actual_profit
            FROM trade_batches
            WHERE status = 'completed'
            """
        )
        total_batches = len(rows)
        if total_batches == 0:
            return {
                "total_batches": 0,
                "total_expected": 0.0,
                "total_actual": 0.0,
                "avg_profit": 0.0,
                "success_rate": 0.0,
            }
        total_expected = sum(r["expected_profit"] or 0.0 for r in rows)
        total_actual = sum(r["actual_profit"] or 0.0 for r in rows)
        avg_profit = total_actual / total_batches
        profitable = sum(1 for r in rows if (r["actual_profit"] or 0.0) > 0)
        success_rate = (profitable / total_batches) * 100.0

        return {
            "total_batches": total_batches,
            "total_expected": total_expected,
            "total_actual": total_actual,
            "avg_profit": avg_profit,
            "success_rate": success_rate,
        }


    def update_item_progress(
        self,
        item_id: int,
        bought_qty: int,
        sold_qty: int,
        buy_spent: float,
        sell_received: float,
        status: str,
        sold_at: Optional[str] = None,
        time_to_sell_days: Optional[float] = None,
    ) -> None:
        self.db.execute(
            """
            UPDATE trade_batch_items
            SET bought_qty = ?, sold_qty = ?, buy_spent = ?,
                sell_received = ?, status = ?,
                sold_at = COALESCE(?, sold_at),
                time_to_sell_days = COALESCE(?, time_to_sell_days)
            WHERE item_id = ?
            """,
            (bought_qty, sold_qty, buy_spent, sell_received, status, sold_at, time_to_sell_days, item_id),
        )

    def set_item_override(self, item_id: int, override: Optional[str]) -> None:
        self.db.execute(
            "UPDATE trade_batch_items SET status_override = ? WHERE item_id = ?",
            (override or "", item_id),
        )
        self.logger.info("Item %s override set to %r", item_id, override or "")

    def complete_batch(self, batch_id: int, actual_profit: float) -> None:
        self.db.execute(
            """
            UPDATE trade_batches
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP,
                actual_profit = ?
            WHERE batch_id = ?
            """,
            (actual_profit, batch_id),
        )
        self.logger.info("Batch %s marked as completed", batch_id)

    def delete_batch(self, batch_id: int) -> None:
        self.db.execute(
            "DELETE FROM trade_batch_items WHERE batch_id = ?",
            (batch_id,),
        )
        self.db.execute(
            "DELETE FROM trade_batches WHERE batch_id = ?",
            (batch_id,),
        )
        self.logger.info("Deleted batch %s and its items", batch_id)