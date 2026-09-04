# FILE: app/services/batch_tracker.py
# VERSION: 1.2.0

import logging
from datetime import datetime
from typing import Callable, List, Optional

from app.db.database import Database
from app.db.wallet_repository import WalletRepository
from app.db.trade_batch_repository import TradeBatchRepository
from app.db.characters_repository import CharactersRepository
from app.db.contract_repository import ContractRepository
from app.esi.contract_service import haul_state
from app.settings.app_settings import AppSettings

logger = logging.getLogger("app.services.batch_tracker")

TERMINAL_STATUSES = ("sold", "lost")


class BatchTracker:
    """
    Syncs wallet transactions for batch characters and updates
    batch item progress + completion scorecard.

    Contract-aware: the latest courier contract on the trade route
    drives haul status; a failed haul marks unsold goods as lost
    (gank/delivery-failure) so the loss lands in actual profit.
    """

    def __init__(
        self,
        db: Database,
        wallet_repo: WalletRepository,
        batch_repo: TradeBatchRepository,
        characters_repo: CharactersRepository,
        client_factory: Callable,
        settings: Optional[AppSettings] = None,
        contract_repo: Optional[ContractRepository] = None,
    ):
        self.db = db
        self.wallet_repo = wallet_repo
        self.batch_repo = batch_repo
        self.characters_repo = characters_repo
        self.client_factory = client_factory
        self.settings = settings
        self.contract_repo = contract_repo

    def sync_active(self) -> List[str]:
        summary: List[str] = []
        batches = self.batch_repo.get_active_batches()
        if not batches:
            return ["No active batches to track."]

        char_ids = set()
        for batch in batches:
            for cid in (batch.buy_char_id, batch.sell_char_id):
                if cid:
                    char_ids.add(cid)

        for cid in char_ids:
            summary.extend(self._sync_character(cid))

        route_haul = self._route_haul_state()
        for batch in batches:
            batch.haul_state = route_haul or ""
            summary.extend(self._update_batch(batch))
        return summary

    def _route_haul_state(self) -> Optional[str]:
        if not self.settings or not self.contract_repo:
            return None
        buy_char = self.settings.trade_buy_character_id
        start = self.settings.trade_buy_station_id or 0
        end = self.settings.trade_sell_station_id or 0
        if not (buy_char and start and end):
            return None

        hauls = [
            r for r in self.contract_repo.get_contracts(contract_type="courier")
            if r.get("issuer_id") == buy_char
            and r.get("start_location_id") == start
            and r.get("end_location_id") == end
        ]
        if not hauls:
            return None
        hauls.sort(key=lambda r: r.get("date_issued") or "", reverse=True)
        return haul_state(hauls[0].get("status"))

    def _sync_character(self, character_id: int) -> List[str]:
        character = self.characters_repo.get_character(character_id)
        if character is None or not character.esi_refresh_token:
            return [f"Char {character_id}: no token, skipped."]

        client = self.client_factory(character)
        if client is None:
            return [f"{character.character_name}: no client."]

        added = 0
        for page in range(1, 11):
            try:
                rows = client.get_wallet_transactions(page)
                if not rows:
                    break
                ids = [r.get("transaction_id", 0) for r in rows]
                known = self.wallet_repo.known_ids(ids)
                new_rows = [
                    r for r in rows
                    if r.get("transaction_id", 0) not in known
                ]
                added += self.wallet_repo.upsert_transactions(
                    character_id, new_rows
                )
                if not new_rows:
                    break
            except Exception as exc:
                logger.exception("Wallet sync failed for %s", character_id)
                return [f"{character.character_name}: sync error."]

        self.wallet_repo.purge_old()
        logger.info(
            "Wallet sync for %s: %s new transactions",
            character.character_name,
            added,
        )
        return [f"{character.character_name}: {added} new tx"]

    def _auto_status(
        self, item, bought: int, sold: int, haul: Optional[str]
    ) -> str:
        if item.quantity > 0 and sold >= item.quantity:
            return "sold"
        if haul == "failed" and bought > 0:
            return "lost"
        if item.quantity > 0 and bought >= item.quantity:
            if haul in ("waiting", "in_transit"):
                return "hauling"
            return "bought"
        if bought > 0:
            return "buying"
        return "pending"

    def _update_batch(self, batch) -> List[str]:
        since = batch.created_at.replace(" ", "T")
        all_terminal = True
        actual = 0.0
        lines: List[str] = []

        for item in batch.items:
            if batch.buy_char_id:
                bought, spent = self.wallet_repo.sums(
                    batch.buy_char_id, item.type_id, True, since
                )
            else:
                bought, spent = 0, 0.0
            if batch.sell_char_id:
                sold, received = self.wallet_repo.sums(
                    batch.sell_char_id, item.type_id, False, since
                )
            else:
                sold, received = 0, 0.0

            if item.status_override:
                status = item.status_override
            else:
                status = self._auto_status(
                    item, bought, sold, batch.haul_state or None
                )

            sold_at = item.sold_at
            time_to_sell = item.time_to_sell_days
            if status == "sold" and not sold_at:
                sold_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                if batch.created_at:
                    try:
                        fmt = "%Y-%m-%d %H:%M:%S"
                        c_dt = datetime.strptime(batch.created_at, fmt)
                        s_dt = datetime.strptime(sold_at, fmt)
                        delta = s_dt - c_dt
                        time_to_sell = max(0.0, delta.total_seconds() / 86400.0)
                    except Exception:
                        time_to_sell = 0.0

            self.batch_repo.update_item_progress(
                item.item_id, bought, sold, spent, received, status,
                sold_at=sold_at if status == "sold" else None,
                time_to_sell_days=time_to_sell if status == "sold" else None,
            )
            item.bought_qty = bought
            item.sold_qty = sold
            item.buy_spent = spent
            item.sell_received = received
            item.status = status
            item.sold_at = sold_at or item.sold_at
            item.time_to_sell_days = time_to_sell if status == "sold" else item.time_to_sell_days

            actual += received - spent
            if status not in TERMINAL_STATUSES:
                all_terminal = False

        lines.append(f"Batch #{batch.batch_id}: actual {actual:,.0f} ISK")
        if batch.haul_state == "failed":
            lines.append(
                f"Batch #{batch.batch_id}: HAUL FAILED - unsold goods marked lost."
            )

        if all_terminal and batch.items:
            self.batch_repo.complete_batch(batch.batch_id, actual)
            lines.append(f"Batch #{batch.batch_id} completed.")
        return lines