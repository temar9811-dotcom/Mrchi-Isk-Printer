# FILE: app/services/trade_calculator.py
# VERSION: 1.17.0
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Set
from app.esi.market_service import MarketService
from app.esi.universe_resolver import UniverseResolver
from app.models.trade_batch import TradeSuggestion, TradeBatchRecommendation
from app.services.trade_shift import calculate_shift_ratio
from app.services.sell_time_analyzer import SellTimeAnalyzer

logger = logging.getLogger("app.services.trade_calculator")

_shift_ratios_log = []


POPULAR_TRADE_TYPES = [
    34, 35, 36, 37, 38, 39, 40, 16272, 16274, 16275, 29668, 31316, 4247, 4312,
]
STRUCTURE_ID_THRESHOLD = 1_000_000_000
MAX_CANDIDATE_TYPES = 200
CALC_WORKERS = 8
TREND_MIN = 0.5
TREND_MAX = 1.5


class TradeCalculator:
    def __init__(self, market_service: MarketService, resolver: UniverseResolver):
        self.market = market_service
        self.resolver = resolver
        self._sell_time_stats = {}
        if hasattr(market_service, "db") and market_service.db is not None:
            try:
                analyzer = SellTimeAnalyzer(market_service.db)
                self._sell_time_stats = analyzer.get_sell_time_stats()
            except Exception as exc:
                logger.warning("Could not load sell time stats: %s", exc)

    def _location_orders(self, region_id, location_id, type_id, access_token, cache_only) -> List:
        if location_id and location_id >= STRUCTURE_ID_THRESHOLD:
            try:
                return self.market.get_orders(
                    "structure", location_id, type_id,
                    access_token=access_token, cache_only=cache_only,
                )
            except Exception as exc:
                logger.warning("Structure market fetch failed for %s: %s", location_id, exc)
                return []
        region_orders = self.market.get_orders(
            "region", region_id, type_id, cache_only=cache_only
        )
        if location_id:
            return [o for o in region_orders if o.location_id == location_id]
        return region_orders

    @staticmethod
    def hauling_cost(volume_m3, per_m3, min_charge, full_load_charge, capacity=320_000.0) -> float:
        if volume_m3 <= 0:
            return 0.0
        if capacity > 0 and volume_m3 >= capacity:
            return full_load_charge
        total = volume_m3 * per_m3
        if total < min_charge:
            return min_charge
        if total > full_load_charge:
            return full_load_charge
        return total
    @staticmethod
    def _calculate_shift_ratio(history) -> float:
        return calculate_shift_ratio(history)



    @staticmethod
    def _sellable_from_history(history, cycle_days: int, share_pct: float) -> int:
        rows = sorted(history, key=lambda r: r.date, reverse=True)
        period = max(1, int(cycle_days))
        window = rows[:period]
        period_vol = sum(r.volume for r in window)
        if period_vol <= 0:
            return 0
        half = max(1, period // 2)
        recent = window[:half]
        prior = window[half:period]
        trend = 1.0
        if prior and recent:
            recent_avg = sum(r.average for r in recent) / len(recent)
            prior_avg = sum(r.average for r in prior) / len(prior)
            if prior_avg > 0:
                trend = max(TREND_MIN, min(TREND_MAX, recent_avg / prior_avg))
        return int(period_vol * trend * (share_pct / 100.0))

    @staticmethod
    def _calculate_fill_position(buy_orders: List, sell_orders: List, history, cycle_days: int) -> float:
        """
        Determine where volume actually went by comparing history avg to VWAPs.
        Returns 0.0-1.0 where:
        - 0.0 = all volume went to buy orders (instant sells)
        - 0.5 = mixed
        - 1.0 = all volume went to sell orders (instant buys)
        """
        buy_vwap = 0.0
        sell_vwap = 0.0
        buy_vol = sum(o.volume_remain for o in buy_orders if o.volume_remain > 0)
        sell_vol = sum(o.volume_remain for o in sell_orders if o.volume_remain > 0)
        
        if buy_vol > 0:
            buy_vwap = sum(o.price * o.volume_remain for o in buy_orders if o.volume_remain > 0) / buy_vol
        if sell_vol > 0:
            sell_vwap = sum(o.price * o.volume_remain for o in sell_orders if o.volume_remain > 0) / sell_vol
        
        if buy_vwap <= 0 or sell_vwap <= 0 or sell_vwap <= buy_vwap:
            return 0.5
        
        rows = sorted(history, key=lambda r: r.date, reverse=True)
        period = max(1, int(cycle_days))
        window = rows[:period]
        if not window:
            return 0.5
        history_avg = sum(r.average for r in window) / len(window)
        
        position = (history_avg - buy_vwap) / (sell_vwap - buy_vwap)
        return max(0.0, min(1.0, position))

    @staticmethod
    def _blended_instant_sell_price(buy_orders: List, target_qty: int) -> tuple:
        sorted_orders = sorted(
            [o for o in buy_orders if o.volume_remain > 0],
            key=lambda o: o.price,
            reverse=True,
        )
        total_revenue = 0.0
        filled_qty = 0
        for order in sorted_orders:
            if filled_qty >= target_qty:
                break
            take = min(order.volume_remain, target_qty - filled_qty)
            total_revenue += take * order.price
            filled_qty += take
        if filled_qty == 0:
            return 0.0, 0
        blended = total_revenue / filled_qty
        return blended, filled_qty

    def calculate(
        self,
        buy_region: int,
        buy_loc: int,
        sell_region: int,
        sell_loc: int,
        cycle_days: int,
        max_items: int,
        haul_per_m3: float,
        haul_min_charge: float,
        haul_full_load: float,
        exclude_types: Set[int] = None,
        blacklist: Set[int] = None,
        access_token: Optional[str] = None,
        instant_buy: bool = False,
        instant_sell: bool = False,
        both_modes: bool = False,
        invert: bool = False,
        haul_capacity: int = 320_000,
        budget_isk: float = 0.0,
        market_share_pct: float = 5.0,
        buy_fee_frac: float = 0.0,
        sell_fee_frac: float = 0.0,
        cache_only: bool = True,
        tax_pct: float = 0.0,
    ) -> List[TradeBatchRecommendation]:
        if exclude_types is None:
            exclude_types = set()
        if blacklist is None:
            blacklist = set()
        if invert:
            buy_region, sell_region = sell_region, buy_region
            buy_loc, sell_loc = sell_loc, buy_loc
        if buy_loc and buy_loc < STRUCTURE_ID_THRESHOLD:
            resolved = self.resolver.get_region_id_for_location(buy_loc, access_token)
            if resolved:
                buy_region = resolved
        if sell_loc and sell_loc < STRUCTURE_ID_THRESHOLD:
            resolved = self.resolver.get_region_id_for_location(sell_loc, access_token)
            if resolved:
                sell_region = resolved
        candidates = set(POPULAR_TRADE_TYPES)
        for loc in (buy_loc, sell_loc):
            if loc and loc >= STRUCTURE_ID_THRESHOLD:
                try:
                    book = self.market.get_structure_orders_all(
                        loc, access_token, cache_only=cache_only
                    )
                    candidates.update(o.type_id for o in book if o.type_id)
                except Exception as exc:
                    logger.warning("Candidate book fetch failed for %s: %s", loc, exc)
        candidate_list = [
            t for t in sorted(candidates)
            if t not in blacklist and t not in exclude_types
        ][:MAX_CANDIDATE_TYPES]
        logger.info(
            "Evaluating %s candidates (cache_only=%s, share=%.1f%%, both=%s)",
            len(candidate_list), cache_only, market_share_pct, both_modes,
        )
        ctx = {
            "buy_region": buy_region, "buy_loc": buy_loc,
            "sell_region": sell_region, "sell_loc": sell_loc,
            "cycle_days": cycle_days,
            "haul_per_m3": haul_per_m3, "haul_min_charge": haul_min_charge,
            "haul_full_load": haul_full_load, "haul_capacity": haul_capacity,
            "budget_isk": budget_isk, "access_token": access_token,
            "instant_buy": instant_buy, "instant_sell": instant_sell,
            "both_modes": both_modes,
            "cache_only": cache_only, "share_pct": market_share_pct,
            "buy_fee_frac": buy_fee_frac, "sell_fee_frac": sell_fee_frac,
            "tax_pct": tax_pct,
        }
        _shift_ratios_log.clear()
        suggestions = []
        with ThreadPoolExecutor(max_workers=CALC_WORKERS) as executor:
            for result in executor.map(
                lambda tid: self._evaluate_type(tid, ctx), candidate_list
            ):
                if result is not None:
                    suggestions.extend(result)
        if _shift_ratios_log:
            examples = _shift_ratios_log[:5]
            example_str = ", ".join(f"{tid}={ratio:.2f}" for tid, ratio in examples)
            logger.debug("Evaluated %s types, shift_ratio examples: %s", len(_shift_ratios_log), example_str)
        suggestions.sort(key=lambda s: s.net_profit, reverse=True)
        profitable = [s for s in suggestions if s.net_profit > 0]
        if not profitable and suggestions:
            return self._group_into_batches(suggestions[:5], 1, haul_capacity, budget_isk)
        return self._group_into_batches(
            profitable[:max_items * 2], max_items, haul_capacity, budget_isk
        )

    def _evaluate_type(self, type_id: int, ctx: dict) -> Optional[List[TradeSuggestion]]:
        try:
            info = self.market.get_type_info(type_id)
            history = self.market.get_history(
                ctx["sell_region"], type_id, cache_only=ctx["cache_only"]
            )
            sellable = self._sellable_from_history(
                history, ctx["cycle_days"], ctx["share_pct"]
            )
            shift_ratio = self._calculate_shift_ratio(history)
            _shift_ratios_log.append((type_id, shift_ratio))

            sell_stats = self._sell_time_stats.get(type_id)
            if sell_stats and sell_stats["sample_count"] >= 3:
                avg_time = sell_stats["avg_time_to_sell"]
                cycle_d = float(ctx["cycle_days"])
                if avg_time > cycle_d and cycle_d > 0:
                    factor = cycle_d / avg_time
                    old_sellable = sellable
                    sellable = int(sellable * factor)
                    logger.debug(
                        "Type %s: sell time adjustment (avg_time=%.1f > cycle=%.1f), sellable reduced %s -> %s",
                        type_id, avg_time, cycle_d, old_sellable, sellable
                    )
                elif avg_time < cycle_d and cycle_d > 0:
                    factor = min(1.3, cycle_d / avg_time)
                    old_sellable = sellable
                    sellable = int(sellable * factor)
                    logger.debug(
                        "Type %s: sell time adjustment (avg_time=%.1f < cycle=%.1f), sellable boosted %s -> %s",
                        type_id, avg_time, cycle_d, old_sellable, sellable
                    )

            buy_loc_orders = self._location_orders(
                ctx["buy_region"], ctx["buy_loc"], type_id,
                ctx["access_token"], ctx["cache_only"],
            )
            sell_loc_orders = self._location_orders(
                ctx["sell_region"], ctx["sell_loc"], type_id,
                ctx["access_token"], ctx["cache_only"],
            )
            
            buy_pool = [o for o in buy_loc_orders if o.is_buy_order and o.volume_remain > 0]
            sell_pool = [o for o in sell_loc_orders if not o.is_buy_order and o.volume_remain > 0]
            instant_sell_pool = [o for o in sell_loc_orders if o.is_buy_order and o.volume_remain > 0]
            
            fill_position = self._calculate_fill_position(
                buy_pool, sell_pool, history, ctx["cycle_days"]
            )
            logger.debug(
                "Type %s: fill_position=%.2f (0=buy orders, 1=sell orders)",
                type_id, fill_position,
            )
            
            if ctx["instant_buy"]:
                buy_pool = [o for o in buy_loc_orders if not o.is_buy_order and o.volume_remain > 0]
            if not buy_pool:
                return None
            if ctx["instant_buy"]:
                best = min(buy_pool, key=lambda o: o.price)
                buy_avail = best.volume_remain
            else:
                best = max(buy_pool, key=lambda o: o.price)
                buy_avail = 1_000_000_000
            buy_price = best.price

            results = []
            modes_to_try = []
            if ctx["both_modes"]:
                modes_to_try = [("placed", False), ("instant", True)]
            elif ctx["instant_sell"]:
                modes_to_try = [("instant", True)]
            else:
                modes_to_try = [("placed", False)]

            for mode_name, is_instant in modes_to_try:
                if is_instant:
                    if not instant_sell_pool:
                        continue
                    max_reasonable = min(buy_avail, sellable, 10000)
                    if ctx["budget_isk"] > 0 and buy_price > 0:
                        max_reasonable = min(max_reasonable, int(ctx["budget_isk"] / buy_price))
                    if max_reasonable <= 0:
                        continue
                    blended_price, fillable_qty = self._blended_instant_sell_price(
                        instant_sell_pool, max_reasonable
                    )
                    if fillable_qty == 0 or blended_price <= buy_price:
                        continue
                    sell_price = blended_price
                    sell_avail = fillable_qty
                    base_sellable = int(sellable * (0.5 + (1 - fill_position) * 0.5))
                    if shift_ratio < 1.0:
                        adjusted_sellable = base_sellable
                    else:
                        adjusted_sellable = base_sellable
                else:
                    if not sell_pool:
                        continue
                    best = min(sell_pool, key=lambda o: o.price)
                    sell_price = best.price
                    sell_avail = 1_000_000_000
                    base_sellable = int(sellable * (0.5 + fill_position * 0.5))
                    if shift_ratio < 1.0:
                        adjusted_sellable = int(base_sellable * max(0.5, shift_ratio))
                    elif shift_ratio > 1.0:
                        adjusted_sellable = int(base_sellable * min(1.5, shift_ratio))
                    else:
                        adjusted_sellable = base_sellable
                
                if sell_price <= buy_price:
                    continue
                if info.volume and info.volume > 0:
                    max_load_qty = int(ctx["haul_capacity"] / info.volume)
                else:
                    max_load_qty = 1_000_000_000
                qty = min(buy_avail, sell_avail, adjusted_sellable, max_load_qty)
                if ctx["budget_isk"] > 0 and buy_price > 0:
                    qty = min(qty, int(ctx["budget_isk"] / buy_price))
                if qty <= 0:
                    continue
                buy_cost = qty * buy_price
                sell_rev = qty * sell_price
                gross_profit = sell_rev - buy_cost
                vol_m3 = qty * info.volume
                haul_cost = self.hauling_cost(
                    vol_m3, ctx["haul_per_m3"], ctx["haul_min_charge"],
                    ctx["haul_full_load"], float(ctx["haul_capacity"]),
                )
                tax_cost = buy_cost * ctx["buy_fee_frac"] + sell_rev * ctx["sell_fee_frac"]
                if ctx["tax_pct"] > 0:
                    tax_cost = (buy_cost + sell_rev) * (ctx["tax_pct"] / 100.0)
                net_profit = gross_profit - haul_cost - tax_cost
                profit_m3 = net_profit / vol_m3 if vol_m3 > 0 else 0
                results.append(TradeSuggestion(
                    type_id=type_id, type_name=info.name,
                    volume_per_unit=info.volume,
                    buy_price=buy_price, sell_price=sell_price,
                    quantity=qty, est_sellable=adjusted_sellable,
                    total_volume=vol_m3,
                    buy_cost=buy_cost, sell_revenue=sell_rev,
                    hauling_cost=haul_cost, tax_cost=tax_cost,
                    net_profit=net_profit, profit_per_m3=profit_m3,
                    sell_mode=mode_name,
                    shift_ratio=shift_ratio,
                ))
            return results if results else None
        except Exception as exc:
            logger.warning("Error calculating for %s: %s", type_id, exc)
            return None

    def _group_into_batches(self, suggestions, max_batches, capacity, budget):
        batches = []
        current = TradeBatchRecommendation(
            batch_name=f"Recommended Batch {len(batches) + 1}"
        )
        for s in suggestions:
            over_volume = current.total_volume + s.total_volume > capacity
            over_budget = budget > 0 and current.total_buy + s.buy_cost > budget
            if (over_volume or over_budget) and current.items:
                batches.append(current)
                if len(batches) >= max_batches:
                    break
                current = TradeBatchRecommendation(
                    batch_name=f"Recommended Batch {len(batches) + 1}"
                )
            current.items.append(s)
            current.total_volume += s.total_volume
            current.total_profit += s.net_profit
            current.total_buy += s.buy_cost
        if current.items and len(batches) < max_batches:
            batches.append(current)
        return batches