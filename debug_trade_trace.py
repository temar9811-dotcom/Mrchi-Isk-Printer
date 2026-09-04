# FILE: debug_trade_trace.py
# VERSION: 1.0.0

import argparse
import json
import logging
import math
from pathlib import Path
from typing import Optional

from app.db.database import Database
from app.db.characters_repository import CharactersRepository
from app.db.trade_batch_repository import TradeBatchRepository
from app.esi.esi_client import EsiClient
from app.esi.market_service import MarketService
from app.esi.universe_resolver import UniverseResolver
from app.services.trade_calculator import POPULAR_TRADE_TYPES


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "eve_assistant.db"
FORGE_REGION_ID = 10000002
OXYGEN_ISOTOPES_TYPE_ID = 16274


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def load_settings(db: Database) -> dict:
    row = db.query_one(
        "SELECT value FROM settings WHERE key = ?",
        ("app_settings",),
    )
    if not row:
        return {}
    try:
        return json.loads(row["value"])
    except Exception:
        logging.exception("Failed to parse app_settings JSON")
        return {}


def get_character(repo: CharactersRepository, char_id: Optional[int]):
    if not char_id:
        return None
    try:
        return repo.get_character(int(char_id))
    except Exception:
        logging.exception("Failed loading character %s", char_id)
        return None


def get_valid_token(character, chars_repo: CharactersRepository) -> Optional[str]:
    if character is None:
        return None

    try:
        client = EsiClient(
            character,
            on_token_refresh=lambda c: chars_repo.add_character(c),
        )
        # Debug script only: use private method so citadel location resolution
        # has a fresh token if needed.
        if client._ensure_valid_token():
            return client.character.esi_access_token
    except Exception:
        logging.exception("Failed refreshing token for %s", character.character_name)

    return character.esi_access_token


def resolve_region(
    resolver: UniverseResolver,
    location_id: int,
    token: Optional[str],
    label: str,
) -> int:
    if not location_id:
        print(f"{label} station blank -> using fallback region The Forge ({FORGE_REGION_ID})")
        return FORGE_REGION_ID

    region_id = resolver.get_region_id_for_location(location_id, token)
    if region_id:
        region_name = resolver.resolve_region(region_id)
        print(f"{label} location {location_id} -> region {region_id} ({region_name})")
        return region_id

    print(
        f"WARNING: Could not resolve {label} location {location_id}; "
        f"falling back to The Forge ({FORGE_REGION_ID})"
    )
    return FORGE_REGION_ID


def best_min_price(orders):
    return min((o.price for o in orders), default=None)


def best_max_price(orders):
    return max((o.price for o in orders), default=None)


def fmt_price(value):
    if value is None:
        return "NONE"
    return f"{value:,.2f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tax", type=float, default=3.0, help="Tax percent to test")
    parser.add_argument("--iso", type=float, default=0.0, help="ISK per JF load; 0 = auto oxygen isotope")
    parser.add_argument(
        "--ignore-stations",
        action="store_true",
        help="Ignore station filters and scan full resolved regions",
    )
    args = parser.parse_args()

    setup_logging()

    print("=" * 80)
    print("TRADE TRACE DEBUG")
    print("=" * 80)
    print(f"DB: {DB_PATH}")

    db = Database(DB_PATH)
    db.connect()
    db.init_schema()

    settings = load_settings(db)
    chars_repo = CharactersRepository(db)
    market = MarketService(db)
    resolver = UniverseResolver(db)
    batch_repo = TradeBatchRepository(db)

    buy_char_id = settings.get("trade_buy_character_id")
    sell_char_id = settings.get("trade_sell_character_id")
    buy_loc = int(settings.get("trade_buy_station_id") or 0)
    sell_loc = int(settings.get("trade_sell_station_id") or 0)

    if args.ignore_stations:
        print("\n*** IGNORING STATION FILTERS FOR THIS RUN ***")
        buy_loc = 0
        sell_loc = 0

    buy_char = get_character(chars_repo, buy_char_id)
    sell_char = get_character(chars_repo, sell_char_id)

    buy_token = get_valid_token(buy_char, chars_repo)
    sell_token = get_valid_token(sell_char, chars_repo)

    print("\n=== Settings ===")
    print(f"Buy char:     {buy_char_id} | {buy_char.character_name if buy_char else 'NONE'}")
    print(f"Sell char:    {sell_char_id} | {sell_char.character_name if sell_char else 'NONE'}")
    print(f"Buy station:  {buy_loc or 'BLANK / REGION'}")
    print(f"Sell station: {sell_loc or 'BLANK / REGION'}")
    print(f"Tax:          {args.tax:.2f}%")

    if buy_loc and sell_loc and buy_loc == sell_loc:
        print("\nWARNING: Buy and sell stations are identical. Profitable instant trades are unlikely.")

    print("\n=== Region Resolution ===")
    buy_region = resolve_region(resolver, buy_loc, buy_token or sell_token, "BUY")
    sell_region = resolve_region(resolver, sell_loc, sell_token or buy_token, "SELL")

    iso_cost = args.iso
    if iso_cost <= 0:
        try:
            iso_price = market.get_best_sell_price(FORGE_REGION_ID, OXYGEN_ISOTOPES_TYPE_ID)
            iso_cost = iso_price * 5000
            print(f"\nAuto ISO: Oxygen isotope {iso_price:,.2f} ISK x 5000 = {iso_cost:,.0f} ISK/load")
        except Exception as exc:
            print(f"\nWARNING: Failed auto isotope price: {exc}")
            iso_cost = 0.0
    else:
        print(f"\nManual ISO/load: {iso_cost:,.0f}")

    active_types = batch_repo.get_active_type_ids()
    print("\n=== Active Batch Exclusions ===")
    print(f"Excluded type count: {len(active_types)}")
    if active_types:
        print(f"Excluded type IDs: {sorted(active_types)}")

    print("\n=== Per-Type Trace ===")
    profitable = []

    for type_id in POPULAR_TRADE_TYPES:
        print("-" * 80)
        print(f"TYPE {type_id}")

        if type_id in active_types:
            print("SKIP: type is excluded by active batch")
            continue

        try:
            info = market.get_type_info(type_id)
            print(f"Name: {info.name} | volume/unit: {info.volume}")
        except Exception as exc:
            print(f"FAIL: get_type_info: {exc}")
            continue

        try:
            history = market.get_history(sell_region, type_id)
            monthly_vol = sum(
                r.volume for r in sorted(history, key=lambda r: r.date, reverse=True)[:30]
            )
            print(f"History rows: {len(history)} | 30d movement: {monthly_vol:,.0f}")
        except Exception as exc:
            print(f"WARN: history failed: {exc}")
            monthly_vol = 0

        try:
            buy_region_orders = market.get_orders("region", buy_region, type_id)
            sell_region_orders = market.get_orders("region", sell_region, type_id)
        except Exception as exc:
            print(f"FAIL: get_orders: {exc}")
            continue

        region_sell_orders = [
            o for o in buy_region_orders if not o.is_buy_order and o.volume_remain > 0
        ]
        region_buy_orders = [
            o for o in sell_region_orders if o.is_buy_order and o.volume_remain > 0
        ]

        station_sell_orders = region_sell_orders
        station_buy_orders = region_buy_orders

        if buy_loc:
            station_sell_orders = [
                o for o in station_sell_orders if o.location_id == buy_loc
            ]
        if sell_loc:
            station_buy_orders = [
                o for o in station_buy_orders if o.location_id == sell_loc
            ]

        print(
            f"Buy-region sell orders: {len(region_sell_orders)} | "
            f"best region sell: {fmt_price(best_min_price(region_sell_orders))}"
        )
        print(
            f"Sell-region buy orders: {len(region_buy_orders)} | "
            f"best region buy: {fmt_price(best_max_price(region_buy_orders))}"
        )

        if buy_loc:
            print(
                f"BUY STATION sell orders @ {buy_loc}: {len(station_sell_orders)} | "
                f"best: {fmt_price(best_min_price(station_sell_orders))}"
            )
        if sell_loc:
            print(
                f"SELL STATION buy orders @ {sell_loc}: {len(station_buy_orders)} | "
                f"best: {fmt_price(best_max_price(station_buy_orders))}"
            )

        if not station_sell_orders:
            if region_sell_orders:
                print("SKIP: region has sell orders, but none at the configured BUY station")
            else:
                print("SKIP: no sell orders in buy region")
            continue

        if not station_buy_orders:
            if region_buy_orders:
                print("SKIP: region has buy orders, but none at the configured SELL station")
            else:
                print("SKIP: no buy orders in sell region")
            continue

        best_sell = min(station_sell_orders, key=lambda o: o.price)
        best_buy = max(station_buy_orders, key=lambda o: o.price)

        buy_price = best_sell.price
        sell_price = best_buy.price
        spread = sell_price - buy_price

        print(f"Candidate: buy {buy_price:,.2f} -> sell {sell_price:,.2f} | spread {spread:,.2f}")

        if sell_price <= buy_price:
            print("SKIP: sell price <= buy price")
            continue

        competitors = max(1, len(station_sell_orders))
        max_fill = (monthly_vol / competitors) if monthly_vol > 0 else 0

        qty = min(
            best_sell.volume_remain,
            best_buy.volume_remain,
            int(max_fill),
        )

        print(
            f"Qty calc: sell_remain={best_sell.volume_remain:,}, "
            f"buy_remain={best_buy.volume_remain:,}, "
            f"max_fill={max_fill:,.0f} -> qty={qty:,}"
        )

        if qty <= 0:
            print("SKIP: qty <= 0, usually missing/zero market history")
            continue

        buy_cost = qty * buy_price
        sell_revenue = qty * sell_price
        gross_profit = sell_revenue - buy_cost
        volume_m3 = qty * info.volume
        loads = math.ceil(volume_m3 / 320_000) if volume_m3 > 0 else 1
        haul_cost = loads * iso_cost
        tax_cost = (buy_cost + sell_revenue) * (args.tax / 100.0)
        net = gross_profit - haul_cost - tax_cost

        print(
            f"Financials: gross={gross_profit:,.0f}, tax={tax_cost:,.0f}, "
            f"haul={haul_cost:,.0f}, net={net:,.0f}, volume={volume_m3:,.0f} m3"
        )

        if net <= 0:
            print("SKIP: net profit <= 0 after tax/haul")
            continue

        print("PASS: profitable")
        profitable.append((net, info.name, qty, buy_price, sell_price, volume_m3))

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if not profitable:
        print("No profitable trades found by trace.")
        print("\nMost likely causes:")
        print("1. No BUY orders at your configured sell station.")
        print("2. No SELL orders at your configured buy station.")
        print("3. Sell price <= buy price after exact station filtering.")
        print("4. 30d history is 0/missing, causing qty=0.")
        print("5. Tax/haul cost wipes out the spread.")
        print("\nTry:")
        print("  python debug_trade_trace.py --ignore-stations")
        print("If that finds trades, your station filters are the blocker.")
    else:
        profitable.sort(reverse=True)
        for net, name, qty, buy_price, sell_price, volume_m3 in profitable:
            print(
                f"{name:30s} qty={qty:>12,} "
                f"buy={buy_price:>12,.2f} sell={sell_price:>12,.2f} "
                f"vol={volume_m3:>12,.0f} net={net:>15,.0f}"
            )

    db.close()


if __name__ == "__main__":
    main()