# FILE: debug_contracts.py
# VERSION: 1.0.0
#
# Usage:
#   python debug_contracts.py            -> uses primary character
#   python debug_contracts.py 94667977   -> uses a specific character id

import sys
from pathlib import Path

from app.logging_setup import setup_logging
from app.db.database import Database
from app.settings.settings_repository import SettingsRepository
from app.state.app_state import AppState
from app.esi.esi_client import EsiClient
from app.esi.contract_service import ContractService, haul_state


def main() -> None:
    setup_logging()

    db = Database(Path("data/eve_assistant.db"))
    db.connect()
    db.init_schema()

    app_state = AppState(db, SettingsRepository(db))
    app_state.load_characters()

    if len(sys.argv) > 1:
        char = app_state.get_character(int(sys.argv[1]))
    else:
        char = app_state.get_primary_character()

    if char is None:
        print("No character available.")
        return

    print(f"Syncing contracts for {char.character_name}...")
    client = EsiClient(
        char,
        on_token_refresh=lambda c: app_state.characters_repo.add_character(c),
    )
    if not client._ensure_valid_token():
        print("Could not get a valid token.")
        return

    service = ContractService(db, client)
    summary = service.sync(progress=print)
    print("Sync summary:", summary)

    couriers = [
        c for c in service.repo.get_contracts(contract_type="courier")
    ]
    print(f"\nCourier contracts on file: {len(couriers)}")
    for c in couriers[:10]:
        print(
            f"  #{c['contract_id']} [{haul_state(c['status']):>10}] "
            f"{c['start_location_id']} -> {c['end_location_id']} "
            f"vol={c['volume']:,.0f} issued={c['date_issued'][:10]}"
        )

    exchanges = [
        c for c in service.repo.get_contracts(contract_type="item_exchange")
    ]
    print(f"\nItem exchange contracts on file: {len(exchanges)}")
    for c in exchanges[:5]:
        items = service.repo.get_items(int(c["contract_id"]))
        print(
            f"  #{c['contract_id']} [{c['status']}] price={c['price']:,.2f} "
            f"items={len(items)} title={c['title'][:40]}"
        )

    db.close()


if __name__ == "__main__":
    main()