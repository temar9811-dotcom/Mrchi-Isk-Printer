# FILE: app/db/schema.py
# VERSION: 1.6.0

import logging

logger = logging.getLogger("app.db.schema")

SCHEMA_VERSION = 10

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        version INTEGER NOT NULL,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    f"""
    INSERT INTO schema_version (id, version)
    VALUES (1, {SCHEMA_VERSION})
    ON CONFLICT(id) DO UPDATE SET
        version=excluded.version,
        updated_at=CURRENT_TIMESTAMP
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS characters (
        character_id INTEGER PRIMARY KEY,
        character_name TEXT NOT NULL,
        added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        esi_refresh_token TEXT,
        esi_access_token TEXT,
        esi_token_expires_at TEXT,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS debug_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        event_type TEXT NOT NULL,
        message TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS universe_cache (
        eve_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'unknown',
        fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS types_cache (
        type_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        volume REAL NOT NULL DEFAULT 0,
        market_group_id INTEGER NOT NULL DEFAULT 0,
        fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_cache_meta (
        cache_key TEXT PRIMARY KEY,
        fetched_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_orders_cache (
        order_id INTEGER NOT NULL,
        scope TEXT NOT NULL,
        scope_id INTEGER NOT NULL,
        type_id INTEGER NOT NULL,
        location_id INTEGER NOT NULL,
        is_buy_order INTEGER NOT NULL,
        price REAL NOT NULL,
        volume_total INTEGER NOT NULL,
        volume_remain INTEGER NOT NULL,
        min_volume INTEGER NOT NULL DEFAULT 1,
        duration INTEGER NOT NULL DEFAULT 0,
        issued TEXT NOT NULL,
        PRIMARY KEY (scope, scope_id, order_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_orders_type
    ON market_orders_cache (scope, scope_id, type_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS market_history_cache (
        region_id INTEGER NOT NULL,
        type_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        average REAL NOT NULL,
        highest REAL NOT NULL,
        lowest REAL NOT NULL,
        order_count INTEGER NOT NULL,
        volume REAL NOT NULL,
        PRIMARY KEY (region_id, type_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trade_batches (
        batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
        buy_char_id INTEGER,
        sell_char_id INTEGER,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT,
        expected_profit REAL NOT NULL DEFAULT 0,
        actual_profit REAL NOT NULL DEFAULT 0,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trade_batch_items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        type_id INTEGER NOT NULL,
        type_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        buy_price REAL NOT NULL,
        sell_price REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        bought_qty INTEGER NOT NULL DEFAULT 0,
        sold_qty INTEGER NOT NULL DEFAULT 0,
        buy_spent REAL NOT NULL DEFAULT 0,
        sell_received REAL NOT NULL DEFAULT 0,
        status_override TEXT,
        sold_at TEXT,
        time_to_sell_days REAL,
        FOREIGN KEY (batch_id) REFERENCES trade_batches(batch_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS price_alerts (
        type_id INTEGER PRIMARY KEY,
        type_name TEXT,
        drop_pct REAL,
        current_avg REAL,
        baseline_avg REAL,
        detected_at TEXT,
        active INTEGER DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS wallet_transactions (
        transaction_id INTEGER PRIMARY KEY,
        character_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        type_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        is_buy INTEGER NOT NULL,
        location_id INTEGER,
        client_id INTEGER
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_wallet_tx_char
    ON wallet_transactions (character_id, type_id, is_buy, date)
    """,
    """
    CREATE TABLE IF NOT EXISTS esi_cache (
        cache_key TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        fetched_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trade_blacklist (
        type_id INTEGER PRIMARY KEY,
        type_name TEXT NOT NULL,
        added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS contracts (
        contract_id INTEGER PRIMARY KEY,
        character_id INTEGER NOT NULL,
        issuer_id INTEGER,
        assignee_id INTEGER,
        acceptor_id INTEGER,
        start_location_id INTEGER,
        end_location_id INTEGER,
        title TEXT,
        contract_type TEXT,
        status TEXT,
        availability TEXT,
        date_issued TEXT,
        date_accepted TEXT,
        date_completed TEXT,
        date_expired TEXT,
        price REAL NOT NULL DEFAULT 0,
        reward REAL NOT NULL DEFAULT 0,
        collateral REAL NOT NULL DEFAULT 0,
        buyout REAL NOT NULL DEFAULT 0,
        volume REAL NOT NULL DEFAULT 0,
        days_to_complete INTEGER,
        fetched_at REAL NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_contracts_char
    ON contracts (character_id, contract_type, status)
    """,
    """
    CREATE TABLE IF NOT EXISTS contract_items (
        contract_id INTEGER NOT NULL,
        record_id INTEGER NOT NULL,
        type_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0,
        is_included INTEGER NOT NULL DEFAULT 1,
        is_singleton INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (contract_id, record_id)
    )
    """,
]


def apply_migrations(db) -> None:
    """
    One-time migrations for older databases.
    """
    rows = db.query("PRAGMA table_info(trade_batch_items)")
    columns = {row["name"] for row in rows}

    column_migrations = [
        ("bought_qty",
         "ALTER TABLE trade_batch_items ADD COLUMN bought_qty INTEGER NOT NULL DEFAULT 0"),
        ("sold_qty",
         "ALTER TABLE trade_batch_items ADD COLUMN sold_qty INTEGER NOT NULL DEFAULT 0"),
        ("buy_spent",
         "ALTER TABLE trade_batch_items ADD COLUMN buy_spent REAL NOT NULL DEFAULT 0"),
        ("sell_received",
         "ALTER TABLE trade_batch_items ADD COLUMN sell_received REAL NOT NULL DEFAULT 0"),
        ("status_override",
         "ALTER TABLE trade_batch_items ADD COLUMN status_override TEXT"),
        ("sold_at",
         "ALTER TABLE trade_batch_items ADD COLUMN sold_at TEXT"),
        ("time_to_sell_days",
         "ALTER TABLE trade_batch_items ADD COLUMN time_to_sell_days REAL"),
    ]

    for column, ddl in column_migrations:
        if column not in columns:
            db.execute(ddl)
            logger.info("Migrated trade_batch_items: added column %s", column)

    alert_tables = db.query("SELECT name FROM sqlite_master WHERE type='table' AND name='price_alerts'")
    if not alert_tables:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS price_alerts (
                type_id INTEGER PRIMARY KEY,
                type_name TEXT,
                drop_pct REAL,
                current_avg REAL,
                baseline_avg REAL,
                detected_at TEXT,
                active INTEGER DEFAULT 1
            )
            """
        )
        logger.info("Migrated schema: created table price_alerts")

    rows = db.query("PRAGMA table_info(market_orders_cache)")
    if rows:
        pk_cols = sorted(row["name"] for row in rows if row["pk"] > 0)
        if pk_cols != ["order_id", "scope", "scope_id"]:
            db.execute("DROP TABLE market_orders_cache")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS market_orders_cache (
                    order_id INTEGER NOT NULL,
                    scope TEXT NOT NULL,
                    scope_id INTEGER NOT NULL,
                    type_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    is_buy_order INTEGER NOT NULL,
                    price REAL NOT NULL,
                    volume_total INTEGER NOT NULL,
                    volume_remain INTEGER NOT NULL,
                    min_volume INTEGER NOT NULL DEFAULT 1,
                    duration INTEGER NOT NULL DEFAULT 0,
                    issued TEXT NOT NULL,
                    PRIMARY KEY (scope, scope_id, order_id)
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_orders_type "
                "ON market_orders_cache (scope, scope_id, type_id)"
            )
            db.execute(
                "DELETE FROM market_cache_meta WHERE cache_key LIKE 'orders:%'"
            )
            logger.info("Migrated market_orders_cache to composite primary key")