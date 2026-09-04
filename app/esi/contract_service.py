# FILE: app/esi/contract_service.py
# VERSION: 1.0.0

import logging
from typing import Callable, Dict, List, Optional

from app.db.database import Database
from app.db.contract_repository import ContractRepository
from app.esi.esi_client import EsiClient

logger = logging.getLogger("app.esi.contract_service")

MAX_CONTRACT_PAGES = 10
MAX_ITEM_CONTRACTS = 50

DELIVERED_STATUSES = ("finished", "finished_issuer", "finished_contractor")
FAILED_STATUSES = ("failed",)
CANCELLED_STATUSES = ("cancelled", "rejected", "deleted", "reversed", "expired")
IN_TRANSIT_STATUSES = ("in_progress",)
WAITING_STATUSES = ("outstanding",)


def haul_state(status: str) -> str:
    """
    Normalized haul state for courier contracts.
    """
    s = (status or "").lower()
    if s in DELIVERED_STATUSES:
        return "delivered"
    if s in FAILED_STATUSES:
        return "failed"
    if s in CANCELLED_STATUSES:
        return "cancelled"
    if s in IN_TRANSIT_STATUSES:
        return "in_transit"
    if s in WAITING_STATUSES:
        return "waiting"
    return "unknown"


class ContractService:
    """
    Pulls and stores contracts; classifies JF hauls and item exchanges.
    """

    def __init__(self, db: Database, client: EsiClient):
        self.repo = ContractRepository(db)
        self.client = client

    def sync(self, progress: Optional[Callable[[str], None]] = None) -> Dict:
        def say(msg: str) -> None:
            if progress:
                progress(msg)
            logger.info(msg)

        contracts: List[Dict] = []
        for page in range(1, MAX_CONTRACT_PAGES + 1):
            say(f"Fetching contracts page {page}...")
            batch = self.client.get_contracts(page)
            if not batch:
                break
            contracts.extend(batch)
            if len(batch) < 100:
                break

        self.repo.upsert_contracts(self.client.character.character_id, contracts)
        say(f"Stored {len(contracts)} contracts.")

        relevant = [
            c for c in contracts
            if c.get("type") in ("item_exchange", "courier")
        ][:MAX_ITEM_CONTRACTS]

        items_fetched = 0
        for i, c in enumerate(relevant, 1):
            cid = int(c.get("contract_id", 0))
            try:
                items = self.client.get_contract_items(cid)
                self.repo.upsert_items(cid, items)
                items_fetched += 1
                if i % 10 == 0:
                    say(f"Contract items {i}/{len(relevant)}...")
            except Exception:
                logger.warning("Contract items fetch failed for %s", cid)

        say(f"Fetched items for {items_fetched} contracts.")
        return {"contracts": len(contracts), "item_contracts": items_fetched}

    def hauls_for_route(
        self, issuer_id: int, start_loc: int, end_loc: int
    ) -> List[Dict]:
        """
        Courier contracts issued by `issuer_id` on a given route,
        newest first. These are your JF service hauls.
        """
        rows = self.repo.get_contracts(contract_type="courier")
        return [
            r for r in rows
            if r.get("issuer_id") == issuer_id
            and r.get("start_location_id") == start_loc
            and r.get("end_location_id") == end_loc
        ]

    def latest_haul_state(
        self, issuer_id: int, start_loc: int, end_loc: int
    ) -> Optional[Dict]:
        hauls = self.hauls_for_route(issuer_id, start_loc, end_loc)
        if not hauls:
            return None
        hauls.sort(key=lambda r: r.get("date_issued") or "", reverse=True)
        top = hauls[0]
        top = dict(top)
        top["haul_state"] = haul_state(top.get("status"))
        return top

    def item_exchange_totals(
        self, character_id: int, type_ids: List[int], since_date: str
    ) -> Dict[int, Dict[str, float]]:
        """
        Quantities/values bought or sold via item-exchange contracts,
        per type_id. Used to count contract trades toward batch progress.
        """
        out: Dict[int, Dict[str, float]] = {}
        rows = self.repo.get_contracts(
            character_id=character_id, contract_type="item_exchange"
        )
        wanted = set(type_ids)
        for r in rows:
            if (r.get("date_issued") or "") < since_date:
                continue
            status = (r.get("status") or "").lower()
            if status not in DELIVERED_STATUSES + ("in_progress", "outstanding"):
                continue
            for item in self.repo.get_items(int(r["contract_id"])):
                tid = int(item["type_id"])
                if tid not in wanted or not item["is_included"]:
                    continue
                slot = out.setdefault(
                    tid, {"qty": 0.0, "value": 0.0, "count": 0.0}
                )
                qty = float(item["quantity"])
                slot["qty"] += qty
                slot["value"] += qty * float(r.get("price", 0) or 0)
                slot["count"] += 1
        return out