# FILE: check_market.py
# VERSION: 1.0.0

from pathlib import Path

from app.db.database import Database
from app.esi.market_service import MarketService
from app.logging_setup import setup_logging

REGION_THE_FORGE = 10000002
TYPE_TRITIUM = 34
STATION_JITA_4_4 = 60003760


def main() -> None:
    logger = setup_logging()
    logger.info("Starting market debug script")

    db_path = Path("data/eve_assistant.db")
    db = Database(db_path)

    try:
        db.connect()
        db.init_schema()

        service = MarketService(db)

        print("=== Type Info ===")
        info = service.get_type_info(TYPE_TRITIUM)
        print(f"  Name:   {info.name}")
        print(f"  Volume: {info.volume} m3")

        print("\n=== Region Orders (The Forge, Tritium) ===")
        orders = service.get_orders("region", REGION_THE_FORGE, TYPE_TRITIUM)
        print(f"  Total orders: {len(orders)}")

        station_orders = [
            o for o in orders if o.location_id == STATION_JITA_4_4
        ]

        sell_orders = [o for o in station_orders if not o.is_buy_order]
        buy_orders = [o for o in station_orders if o.is_buy_order]

        if sell_orders:
            best_sell = min(sell_orders, key=lambda o: o.price)
            print(f"  Best sell at Jita 4-4: {best_sell.price:,.2f} ISK")
        else:
            print("  No sell orders at Jita 4-4")

        if buy_orders:
            best_buy = max(buy_orders, key=lambda o: o.price)
            print(f"  Best buy at Jita 4-4:  {best_buy.price:,.2f} ISK")
        else:
            print("  No buy orders at Jita 4-4")

        print("\n=== Market History (last 3 days) ===")
        history = service.get_history(REGION_THE_FORGE, TYPE_TRITIUM)
        recent = sorted(history, key=lambda r: r.date, reverse=True)[:3]

        for row in recent:
            print(
                f"  {row.date} | avg {row.average:,.2f} | "
                f"vol {row.volume:,.0f}"
            )

        monthly = service.get_monthly_volume(REGION_THE_FORGE, TYPE_TRITIUM)
        print(f"\n  30-day movement: {monthly:,.0f} units")

        print("\nMarket debug script completed successfully.")

    except Exception:
        logger.exception("Market debug script failed")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()