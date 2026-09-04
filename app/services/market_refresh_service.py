# FILE: app/services/market_refresh_service.py
# VERSION: 1.1.0

import logging
from typing import Callable, List, Optional, Set

from app.db.database import Database
from app.esi.market_service import MarketService
from app.esi.universe_resolver import UniverseResolver

logger = logging.getLogger("app.services.market_refresh")

STRUCTURE_ID_THRESHOLD = 1_000_000_000
DEFAULT_REGION = 10000002
HISTORY_CAP = 150


class MarketRefreshService:
    """
    Pulls shared market data (order books + histories) into the DB.

    Used by the startup preload (force=False, respects TTLs) and by the
    per-tab Refresh buttons (force=True).
    """

    def __init__(self, db: Database, resolver: UniverseResolver, token: Optional[str]):
        self.db = db
        self.market = MarketService(db)
        self.resolver = resolver
        self.token = token

    def station_region(self, location_id: int) -> int:
        if not location_id:
            return DEFAULT_REGION
        region = self.resolver.get_region_id_for_location(location_id, self.token)
        return region or DEFAULT_REGION

    def pull_station(self, location_id: int, force: bool, progress: Callable[[str], None]) -> None:
        if not location_id:
            return
        if location_id >= STRUCTURE_ID_THRESHOLD:
            progress(f"Pulling structure book {location_id}...")
            self.market.get_structure_orders_all(
                location_id, self.token, force=force
            )
        else:
            region = self.station_region(location_id)
            progress(f"Pulling region {region} order book...")
            self.market.get_region_orders_all(region, force=force)

    def candidate_types(self, buy_loc: int, sell_loc: int, popular: List[int]) -> List[int]:
        types: Set[int] = set(popular)
        for loc in (buy_loc, sell_loc):
            if not loc:
                continue
            scope = "structure" if loc >= STRUCTURE_ID_THRESHOLD else "region_all"
            scope_id = loc if scope == "structure" else self.station_region(loc)
            for order in self.market.repo.get_orders_for_scope(scope, scope_id):
                if order.type_id:
                    types.add(order.type_id)
        return sorted(types)[:HISTORY_CAP]

    def pull_histories(
        self, region_id: int, type_ids: List[int], force: bool,
        progress: Callable[[str], None],
    ) -> None:
        total = len(type_ids)
        for i, type_id in enumerate(type_ids, 1):
            progress(f"History {i}/{total} (type {type_id})...")
            try:
                self.market.get_history(region_id, type_id, force=force)
            except Exception as exc:
                logger.warning("History pull failed for %s: %s", type_id, exc)

    def preload(self, buy_loc: int, sell_loc: int, popular: List[int],
                progress: Callable[[str], None]) -> None:
        """
        Startup preload: respects TTLs so quick restarts stay fast.
        One station failing no longer aborts the rest.
        """
        for loc in {buy_loc, sell_loc}:
            if not loc:
                continue
            try:
                self.pull_station(loc, force=False, progress=progress)
            except Exception as exc:
                logger.exception("Preload failed for station %s", loc)
                progress(f"Station {loc} preload failed: {str(exc)[:40]}")

        region = self.station_region(sell_loc or buy_loc)
        try:
            progress("Checking market histories...")
            self.pull_histories(region, popular, force=False, progress=progress)
        except Exception as exc:
            logger.exception("History preload failed")
            progress(f"History preload failed: {str(exc)[:40]}")

    def refresh_trade_data(self, buy_loc: int, sell_loc: int, popular: List[int],
                           progress: Callable[[str], None]) -> None:
        """
        Manual Market Trade refresh: force books + histories.
        """
        self.pull_station(buy_loc, force=True, progress=progress)
        self.pull_station(sell_loc, force=True, progress=progress)

        region = self.station_region(sell_loc or buy_loc)
        types = self.candidate_types(buy_loc, sell_loc, popular)
        self.pull_histories(region, types, force=True, progress=progress)