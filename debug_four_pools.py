# FILE: debug_four_pools.py
# VERSION: 1.1.0

from pathlib import Path

from app.db.database import Database
from app.db.characters_repository import CharactersRepository
from app.esi.esi_client import EsiClient
from app.esi.market_service import MarketService

DB_PATH = Path("data/eve_assistant.db")
BUY_LOC = 60003760        # Jita 4-4
SELL_LOC = 1049588174021  # Your Insmother citadel
TYPE_ID = 34              # Tritanium
STRUCTURE_THRESHOLD = 1_000_000_000


def get_token(db: Database):
    repo = CharactersRepository(db)
    for char in repo.get_all_characters():
        client = EsiClient(char)
        if client._ensure_valid_token():
            return client.character.esi_access_token
    return None


def location_orders(market, region_id, location_id, token):
    if location_id >= STRUCTURE_THRESHOLD:
        return market.get_orders(
            "structure", location_id, TYPE_ID, access_token=token
        )
    return [
        o for o in market.get_orders("region", region_id, TYPE_ID)
        if o.location_id == location_id
    ]


def main():
    db = Database(DB_PATH)
    db.connect()
    db.init_schema()
    market = MarketService(db)

    token = get_token(db)
    print(f"Token available: {bool(token)}")
    print(f"Checking Type {TYPE_ID} (Tritanium)")

    buy_loc_orders = location_orders(market, 10000002, BUY_LOC, token)
    sell_loc_orders = location_orders(market, 10000009, SELL_LOC, token)

    pool1 = [o for o in buy_loc_orders if not o.is_buy_order]
    pool2 = [o for o in buy_loc_orders if o.is_buy_order]
    pool3 = [o for o in sell_loc_orders if o.is_buy_order]
    pool4 = [o for o in sell_loc_orders if not o.is_buy_order]

    print("\n--- BUY STATION (Jita) ---")
    print(f"Instant Buy pool (sell orders): {len(pool1)}"
          + (f" | best {min(o.price for o in pool1):.2f}" if pool1 else ""))
    print(f"Default Buy pool (buy orders): {len(pool2)}"
          + (f" | best {max(o.price for o in pool2):.2f}" if pool2 else ""))

    print("\n--- SELL STATION (Citadel via structure market) ---")
    print(f"Instant Sell pool (buy orders): {len(pool3)}"
          + (f" | best {max(o.price for o in pool3):.2f}" if pool3 else ""))
    print(f"Default Sell pool (sell orders): {len(pool4)}"
          + (f" | best {min(o.price for o in pool4):.2f}" if pool4 else ""))

    db.close()


if __name__ == "__main__":
    main()