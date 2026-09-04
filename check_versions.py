# FILE: check_versions.py
# VERSION: 1.0.0

from pathlib import Path

EXPECTED = {
    "main.py": "1.3.0",
    "app/db/schema.py": "1.6.0",
    "app/db/database.py": "1.4.0",
    "app/db/wallet_repository.py": "1.0.0",
    "app/db/market_repository.py": "1.4.0",
    "app/db/trade_batch_repository.py": "1.5.0",
    "app/db/universe_cache_repository.py": "1.2.0",
    "app/db/esi_cache_repository.py": "1.0.0",
    "app/db/trade_blacklist_repository.py": "1.0.0",
    "app/db/contract_repository.py": "1.0.0",
    "app/esi/esi_client.py": "1.3.0",
    "app/esi/market_service.py": "1.10.0",
    "app/esi/universe_resolver.py": "1.8.0",
    "app/esi/auth_server.py": "1.1.0",
    "app/esi/auth_flow.py": "1.3.0",
    "app/esi/login_worker.py": "1.2.0",
    "app/esi/scopes.py": "1.1.0",
    "app/esi/contract_service.py": "1.0.0",
    "app/models/trade_batch.py": "1.10.0",
    "app/services/batch_tracker.py": "1.2.0",
    "app/services/trade_calculator.py": "1.17.0",
    "app/services/trade_shift.py": "1.0.0",
    "app/services/sell_time_analyzer.py": "1.0.0",
    "app/services/ignore_groups.py": "1.1.0",
    "app/ui/widgets/ignore_list_dialog.py": "1.1.0",
    "app/services/price_alert_service.py": "1.0.0",
    "app/services/tax_service.py": "1.2.0",
    "app/services/pi_optimizer.py": "1.1.0",
    "app/services/market_refresh_service.py": "1.1.0",
    "app/services/contract_sync_worker.py": "1.0.0",
    "app/settings/app_settings.py": "1.6.0",
    "app/state/app_state.py": "1.8.0",
    "app/ui/main_window.py": "2.9.0",
    "app/ui/settings/general_page.py": "1.2.0",
    "app/ui/widgets/trade_panel.py": "1.23.1",
    "app/ui/widgets/market_browser_widget.py": "1.5.0",
    "app/ui/widgets/batch_list_widget.py": "1.3.0",
    "app/ui/widgets/blacklist_dialog.py": "1.0.0",
    "app/ui/widgets/isk_spinbox.py": "1.0.0",
    "app/ui/widgets/pnl_history_widget.py": "1.0.0",
    "app/ui/widgets/trade_worker.py": "1.1.0",
    "app/ui/widgets/pi_panel.py": "1.5.0",
    "app/ui/widgets/pi_detail_panel.py": "1.3.0",
    "app/ui/widgets/pi_worker.py": "1.1.0",
    "app/ui/widgets/pi_detail_worker.py": "1.1.0",
    "app/utils/__init__.py": "1.0.0",
    "app/utils/formatting.py": "1.1.0",
    "debug_contracts.py": "1.0.0",
}


def main() -> None:
    root = Path(__file__).resolve().parent
    all_ok = True

    for rel, expected in EXPECTED.items():
        path = root / rel

        if not path.exists():
            print(f"MISSING  {rel}")
            all_ok = False
            continue

        head = path.read_text(encoding="utf-8").splitlines()[:2]
        version_line = next((l for l in head if "VERSION" in l), "NO VERSION LINE")

        if expected in version_line:
            print(f"OK       {rel}: {version_line.strip()}")
        else:
            print(f"WRONG    {rel}: {version_line.strip()} (expected {expected})")
            all_ok = False

    print("\nALL FILES CORRECT" if all_ok else "\nFILES NEED ATTENTION")


if __name__ == "__main__":
    main()