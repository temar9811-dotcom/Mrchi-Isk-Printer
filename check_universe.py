# FILE: check_universe.py
# VERSION: 1.0.0

from pathlib import Path

from app.db.database import Database
from app.esi.universe_resolver import UniverseResolver
from app.logging_setup import setup_logging


def main() -> None:
    logger = setup_logging()
    logger.info("Starting universe resolver debug script")

    db_path = Path("data/eve_assistant.db")
    db = Database(db_path)

    try:
        db.connect()
        db.init_schema()

        resolver = UniverseResolver(db)

        # Test with well-known IDs
        test_cases = [
            ("system", 30000142),   # Jita
            ("system", 30002187),   # Amarr
            ("station", 60003760),  # Jita IV - Moon 4 - Caldari Navy Assembly Plant
            ("type", 28850),        # Rhea (Jump Freighter)
            ("type", 643),          # Iteron Mark V
            ("region", 10000002),   # The Forge
        ]

        print("=== Universe Resolver Test ===\n")

        for category, eve_id in test_cases:
            if category == "system":
                name = resolver.resolve_system(eve_id)
            elif category == "station":
                name = resolver.resolve_station(eve_id)
            elif category == "type":
                name = resolver.resolve_type(eve_id)
            elif category == "region":
                name = resolver.resolve_region(eve_id)
            else:
                name = "UNKNOWN CATEGORY"

            print(f"  {category:>10} | {eve_id:>12} | {name}")

        print(f"\nCache entries in database: {resolver.cache.count()}")
        print("\nUniverse resolver debug script completed successfully.")

    except Exception:
        logger.exception("Universe resolver debug script failed")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()