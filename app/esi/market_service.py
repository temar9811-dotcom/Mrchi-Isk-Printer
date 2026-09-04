# FILE: app/esi/market_service.py
# VERSION: 1.10.0

import concurrent.futures
import logging
import requests
from typing import List, Optional

from app.db.database import Database
from app.db.market_repository import MarketRepository
from app.models.market_data import MarketHistoryRow, MarketOrder, TypeInfo

logger = logging.getLogger("app.esi.market_service")
ESI_BASE_URL = "https://esi.evetech.net/latest"

ORDERS_TTL_SECONDS = 300
HISTORY_TTL_SECONDS = 3600
MAX_SWEEP_PAGES = 1000
SWEEP_WORKERS = 8


class MarketService:
    def __init__(self, db: Database):
        self.repo = MarketRepository(db)
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def get_type_info(self, type_id: int) -> TypeInfo:
        info = self.repo.get_type(type_id)
        if info and info.name:
            return info
        try:
            resp = self.session.get(f"{ESI_BASE_URL}/universe/types/{type_id}/", timeout=10)
            if resp.status_code == 404:
                return TypeInfo(type_id=type_id, name=f"Type {type_id}", volume=0.0, market_group_id=0)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.exception("Type info fetch failed for %s", type_id)
            return TypeInfo(type_id=type_id, name=f"Type {type_id}", volume=0.0, market_group_id=0)

        info = TypeInfo(
            type_id=type_id,
            name=data.get("name", f"Type {type_id}"),
            volume=float(data.get("volume", 0) or 0),
            market_group_id=int(data.get("market_group_id", 0) or 0),
        )
        self.repo.set_type(info)
        return info

    def _sweep_pages(self, url: str, headers: dict, params_extra: dict = None) -> List[dict]:
        params = {"page": 1}
        if params_extra:
            params.update(params_extra)
        resp = self.session.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        raw_all = list(resp.json())
        try:
            total_pages = int(resp.headers.get("X-Pages", "1") or 1)
        except ValueError:
            total_pages = 1
        capped = min(total_pages, MAX_SWEEP_PAGES)
        if total_pages > capped:
            logger.warning("Sweep of %s has %s pages; capping at %s", url, total_pages, capped)
        if capped > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=SWEEP_WORKERS) as ex:
                futures = [
                    ex.submit(self._fetch_page, url, headers, params_extra, page)
                    for page in range(2, capped + 1)
                ]
                for fut in concurrent.futures.as_completed(futures):
                    rows = fut.result()
                    if rows:
                        raw_all.extend(rows)
        return raw_all

    def _fetch_page(self, url, headers, params_extra, page) -> list:
        params = {"page": page}
        if params_extra:
            params.update(params_extra)
        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("Page %s fetch failed for %s", page, url)
            return []

    def _parse_order(self, raw: dict, type_id: int) -> MarketOrder:
        val = raw.get("is_buy_order", False)
        if isinstance(val, str):
            is_buy = val.lower() in ("1", "true", "t", "yes")
        else:
            is_buy = bool(val)

        return MarketOrder(
            order_id=int(raw.get("order_id", 0)),
            type_id=int(raw.get("type_id", type_id)),
            location_id=int(raw.get("location_id", 0)),
            is_buy_order=is_buy,
            price=float(raw.get("price", 0)),
            volume_total=int(raw.get("volume_total", 0)),
            volume_remain=int(raw.get("volume_remain", 0)),
            min_volume=int(raw.get("min_volume", 1)),
            duration=int(raw.get("duration", 0)),
            issued=str(raw.get("issued", "")),
        )

    def get_orders(
        self, scope, scope_id, type_id, access_token=None,
        force=False, cache_only=False, ttl=ORDERS_TTL_SECONDS,
    ) -> List[MarketOrder]:
        if scope == "structure":
            all_orders = self.get_structure_orders_all(
                scope_id, access_token, force=force, cache_only=cache_only, ttl=ttl
            )
            return [o for o in all_orders if o.type_id == type_id]
        if cache_only:
            return self.repo.get_orders(scope, scope_id, type_id)
        key = f"orders:region:{scope_id}:{type_id}"
        age = self.repo.get_meta_age(key)
        if not force and age is not None and age < ttl:
            return self.repo.get_orders(scope, scope_id, type_id)
        raw_all = self._sweep_pages(
            f"{ESI_BASE_URL}/markets/{scope_id}/orders/", {}, {"type_id": type_id}
        )
        raw_all = [r for r in raw_all if int(r.get("type_id", type_id)) == type_id]
        orders = [self._parse_order(raw, type_id) for raw in raw_all]
        self.repo.replace_orders(scope, scope_id, type_id, orders)
        self.repo.set_meta(key)
        return orders

    def get_structure_orders_all(
        self, structure_id, access_token=None,
        force=False, cache_only=False, ttl=ORDERS_TTL_SECONDS,
    ) -> List[MarketOrder]:
        if cache_only:
            return self.repo.get_orders_for_scope("structure", structure_id)
        key = f"orders:structure:{structure_id}:all"
        age = self.repo.get_meta_age(key)
        if not force and age is not None and age < ttl:
            return self.repo.get_orders_for_scope("structure", structure_id)
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        # NOTE: ESI structure-market endpoint has NO /orders/ suffix.
        raw_all = self._sweep_pages(
            f"{ESI_BASE_URL}/markets/structures/{structure_id}/", headers
        )
        orders = [self._parse_order(raw, int(raw.get("type_id", 0))) for raw in raw_all]
        self.repo.replace_scope_orders("structure", structure_id, orders)
        self.repo.set_meta(key)
        logger.info("Swept %s orders for structure %s", len(orders), structure_id)
        return orders

    def get_region_orders_all(
        self, region_id, force=False, cache_only=False, ttl=ORDERS_TTL_SECONDS,
    ) -> List[MarketOrder]:
        if cache_only:
            return self.repo.get_orders_for_scope("region_all", region_id)
        key = f"orders:region_all:{region_id}"
        age = self.repo.get_meta_age(key)
        if not force and age is not None and age < ttl:
            return self.repo.get_orders_for_scope("region_all", region_id)
        raw_all = self._sweep_pages(f"{ESI_BASE_URL}/markets/{region_id}/orders/", {})
        orders = [self._parse_order(raw, int(raw.get("type_id", 0))) for raw in raw_all]
        self.repo.replace_scope_orders("region_all", region_id, orders)
        self.repo.set_meta(key)
        logger.info("Swept %s orders for region %s", len(orders), region_id)
        return orders

    def get_history(
        self, region_id, type_id, force=False, cache_only=False, ttl=HISTORY_TTL_SECONDS,
    ):
        if cache_only:
            return self.repo.get_history(region_id, type_id)
        key = f"history:{region_id}:{type_id}"
        age = self.repo.get_meta_age(key)
        if not force and age is not None and age < ttl:
            return self.repo.get_history(region_id, type_id)
        try:
            resp = self.session.get(
                f"{ESI_BASE_URL}/markets/{region_id}/history/?type_id={type_id}",
                timeout=15,
            )
        except Exception:
            logger.exception("History fetch failed for %s in %s", type_id, region_id)
            return self.repo.get_history(region_id, type_id)
        if resp.status_code == 404:
            logger.warning("No market history for type %s in region %s", type_id, region_id)
            self.repo.set_meta(key)
            return []
        resp.raise_for_status()
        rows = [
            MarketHistoryRow(
                region_id=region_id, type_id=type_id, date=raw.get("date", ""),
                average=float(raw.get("average", 0)), highest=float(raw.get("highest", 0)),
                lowest=float(raw.get("lowest", 0)), order_count=int(raw.get("order_count", 0)),
                volume=float(raw.get("volume", 0)),
            )
            for raw in resp.json()
        ]
        self.repo.replace_history(region_id, type_id, rows)
        self.repo.set_meta(key)
        return rows

    def get_monthly_volume(self, region_id, type_id) -> float:
        rows = self.get_history(region_id, type_id)
        return sum(r.volume for r in sorted(rows, key=lambda r: r.date, reverse=True)[:30])

    def get_best_sell_price(self, region_id, type_id, location_id=0) -> float:
        orders = self.get_orders("region", region_id, type_id)
        if location_id:
            orders = [o for o in orders if o.location_id == location_id]
        sell_orders = [o for o in orders if not o.is_buy_order and o.volume_remain > 0]
        if not sell_orders:
            return 0.0
        return min(o.price for o in sell_orders)