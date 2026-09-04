# FILE: app/db/market_repository.py
# VERSION: 1.4.0

import logging
import time
from typing import List

from app.db.database import Database
from app.models.market_data import MarketHistoryRow, MarketOrder, TypeInfo


class MarketRepository:
    def __init__(self, db: Database):
        self.db = db
        self.logger = logging.getLogger("app.db.market_repository")

    def get_type(self, type_id: int):
        row = self.db.query_one(
            "SELECT type_id, name, volume, market_group_id "
            "FROM types_cache WHERE type_id = ?",
            (type_id,),
        )
        if row is None:
            return None
        return TypeInfo(
            type_id=row["type_id"],
            name=row["name"],
            volume=row["volume"],
            market_group_id=row["market_group_id"],
        )

    def set_type(self, info: TypeInfo) -> None:
        self.db.execute(
            """
            INSERT INTO types_cache (type_id, name, volume, market_group_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(type_id) DO UPDATE SET
                name=excluded.name,
                volume=excluded.volume,
                market_group_id=excluded.market_group_id,
                fetched_at=CURRENT_TIMESTAMP
            """,
            (info.type_id, info.name, info.volume, info.market_group_id),
        )

    def replace_history(self, region_id, type_id, rows: List[MarketHistoryRow]) -> None:
        self.db.execute(
            "DELETE FROM market_history_cache WHERE region_id = ? AND type_id = ?",
            (region_id, type_id),
        )
        self.db.executemany(
            """
            INSERT INTO market_history_cache (
                region_id, type_id, date, average, highest, lowest,
                order_count, volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.region_id, row.type_id, row.date, row.average,
                    row.highest, row.lowest, row.order_count, row.volume,
                )
                for row in rows
            ],
        )
        self.logger.debug(
            "Cached %s history rows for region %s type %s", len(rows), region_id, type_id
        )

    def get_history(self, region_id, type_id) -> List[MarketHistoryRow]:
        rows = self.db.query(
            """
            SELECT region_id, type_id, date, average, highest, lowest,
                   order_count, volume
            FROM market_history_cache
            WHERE region_id = ? AND type_id = ?
            ORDER BY date
            """,
            (region_id, type_id),
        )
        return [
            MarketHistoryRow(
                region_id=row["region_id"], type_id=row["type_id"], date=row["date"],
                average=row["average"], highest=row["highest"], lowest=row["lowest"],
                order_count=row["order_count"], volume=row["volume"],
            )
            for row in rows
        ]

    def get_meta_age(self, key: str):
        row = self.db.query_one(
            "SELECT fetched_at FROM market_cache_meta WHERE cache_key = ?",
            (key,),
        )
        if row is None:
            return None
        fetched = float(row["fetched_at"])
        return time.time() - fetched

    def get_meta_fetched_at(self, key: str):
        row = self.db.query_one(
            "SELECT fetched_at FROM market_cache_meta WHERE cache_key = ?",
            (key,),
        )
        if row is None:
            return None
        return float(row["fetched_at"])

    def set_meta(self, key: str) -> None:
        self.db.execute(
            """
            INSERT INTO market_cache_meta (cache_key, fetched_at)
            VALUES (?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET fetched_at=excluded.fetched_at
            """,
            (key, time.time()),
        )

    def replace_orders(self, scope, scope_id, type_id, orders: List[MarketOrder]) -> None:
        self.db.execute(
            "DELETE FROM market_orders_cache "
            "WHERE scope = ? AND scope_id = ? AND type_id = ?",
            (scope, scope_id, type_id),
        )
        self._insert_orders(scope, scope_id, orders)
        self.logger.debug(
            "Cached %s orders for %s:%s type %s", len(orders), scope, scope_id, type_id
        )

    def get_orders(self, scope, scope_id, type_id) -> List[MarketOrder]:
        rows = self.db.query(
            """
            SELECT order_id, type_id, location_id, is_buy_order, price,
                   volume_total, volume_remain, min_volume, duration, issued
            FROM market_orders_cache
            WHERE scope = ? AND scope_id = ? AND type_id = ?
            """,
            (scope, scope_id, type_id),
        )
        return [self._row_to_order(row) for row in rows]

    def get_orders_for_scope(self, scope, scope_id) -> List[MarketOrder]:
        rows = self.db.query(
            """
            SELECT order_id, type_id, location_id, is_buy_order, price,
                   volume_total, volume_remain, min_volume, duration, issued
            FROM market_orders_cache
            WHERE scope = ? AND scope_id = ?
            """,
            (scope, scope_id),
        )
        return [self._row_to_order(row) for row in rows]

    def replace_scope_orders(self, scope, scope_id, orders: List[MarketOrder]) -> None:
        self.db.execute(
            "DELETE FROM market_orders_cache WHERE scope = ? AND scope_id = ?",
            (scope, scope_id),
        )
        self._insert_orders(scope, scope_id, orders)
        self.logger.debug(
            "Cached %s orders (all types) for %s:%s", len(orders), scope, scope_id
        )

    def _insert_orders(self, scope, scope_id, orders: List[MarketOrder]) -> None:
        if not orders:
            return
            
        # Deduplicate by order_id just in case ESI returns duplicates across pages
        unique = {o.order_id: o for o in orders}
        
        self.db.executemany(
            """
            INSERT INTO market_orders_cache (
                order_id, scope, scope_id, type_id, location_id, is_buy_order,
                price, volume_total, volume_remain, min_volume, duration, issued
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    order.order_id, scope, scope_id, order.type_id, order.location_id,
                    1 if order.is_buy_order else 0,
                    order.price, order.volume_total, order.volume_remain,
                    order.min_volume, order.duration, order.issued,
                )
                for order in unique.values()
            ],
        )

    def _row_to_order(self, row) -> MarketOrder:
        # Bulletproof boolean parsing for SQLite
        val = row["is_buy_order"]
        if isinstance(val, str):
            is_buy = val.lower() in ("1", "true", "t", "yes")
        else:
            is_buy = bool(val)
            
        return MarketOrder(
            order_id=row["order_id"],
            type_id=row["type_id"],
            location_id=row["location_id"],
            is_buy_order=is_buy,
            price=row["price"],
            volume_total=row["volume_total"],
            volume_remain=row["volume_remain"],
            min_volume=row["min_volume"],
            duration=row["duration"],
            issued=row["issued"],
        )