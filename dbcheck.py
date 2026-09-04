# FILE: check_database.py
# VERSION: 1.0.0

import sqlite3
conn = sqlite3.connect('data/eve_assistant.db')

print("--- Jita 4-4 (60003760) ---")
cur = conn.execute("SELECT is_buy_order, COUNT(*) FROM market_orders_cache WHERE location_id = 60003760 GROUP BY is_buy_order")
print(cur.fetchall())

print("\n--- Total The Forge (10000002) ---")
cur2 = conn.execute("SELECT is_buy_order, COUNT(*) FROM market_orders_cache WHERE scope='region_all' AND scope_id=10000002 GROUP BY is_buy_order")
print(cur2.fetchall())