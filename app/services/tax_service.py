# FILE: app/services/tax_service.py
# VERSION: 1.2.0

import logging
from typing import Dict, Optional, Tuple

from app.esi.esi_client import EsiClient
from app.esi.universe_resolver import UniverseResolver
from app.settings.app_settings import AppSettings

logger = logging.getLogger("app.services.tax_service")

ACCOUNTING_SKILL_ID = 3361
BROKER_RELATIONS_SKILL_ID = 3443

NPC_SALES_TAX_BASE = 2.0
NPC_BROKER_FEE_BASE = 5.0


class TaxService:
    """
    Split-leg market fee model.

    BUY leg:  broker fee only, and only when placing a buy order.
              Uses the BUY character's Broker Relations (NPC stations).
    SELL leg: sales tax always; broker fee when placing a sell order.
              Uses the SELL character's skills (NPC) or citadel
              defaults from settings (player structures).
    """

    def __init__(
        self,
        resolver: UniverseResolver,
        settings: AppSettings,
        buy_client: Optional[EsiClient] = None,
        sell_client: Optional[EsiClient] = None,
    ):
        self.resolver = resolver
        self.settings = settings
        self.buy_client = buy_client
        self.sell_client = sell_client
        self._skill_cache: Dict[int, Dict[int, int]] = {}

    def classify_location(self, location_id: int) -> str:
        name = self.resolver.resolve_station(location_id)
        if name and not name.startswith("Station "):
            return "npc"
        return "citadel"

    def _skill_levels(self, client: Optional[EsiClient]) -> Dict[int, int]:
        if client is None:
            return {}
        char_id = client.character.character_id
        if char_id in self._skill_cache:
            return self._skill_cache[char_id]
        try:
            data = client.get_character_skills()
            levels = {
                s.get("skill_id", 0): s.get("active_skill_level", 0)
                for s in data.get("skills", [])
            }
        except Exception:
            logger.exception("Skill fetch failed for %s", char_id)
            levels = {}
        self._skill_cache[char_id] = levels
        return levels

    def _rates(self, location_id: int, client: Optional[EsiClient]) -> Tuple[float, float]:
        """
        Returns (sales_tax_frac, broker_fee_frac) for a location.
        """
        kind = self.classify_location(location_id)

        if kind == "npc":
            levels = self._skill_levels(client)
            sales = NPC_SALES_TAX_BASE * (
                1.0 - 0.10 * levels.get(ACCOUNTING_SKILL_ID, 0)
            )
            broker = NPC_BROKER_FEE_BASE * (
                1.0 - 0.05 * levels.get(BROKER_RELATIONS_SKILL_ID, 0)
            )
        else:
            sales = float(self.settings.citadel_sales_tax_pct)
            broker = float(self.settings.citadel_broker_fee_pct)

        return sales / 100.0, broker / 100.0

    def buy_leg_fee_frac(self, location_id: int, placed_order: bool) -> float:
        """
        Fraction of buy cost paid as fees (broker fee when placing).
        """
        if not location_id or not placed_order:
            return 0.0
        _, broker = self._rates(location_id, self.buy_client)
        return broker

    def sell_leg_fee_frac(self, location_id: int, placed_order: bool) -> float:
        """
        Fraction of sell revenue paid as fees
        (sales tax always; broker fee when placing).
        """
        if not location_id:
            return 0.0
        sales, broker = self._rates(location_id, self.sell_client)
        return sales + (broker if placed_order else 0.0)

    def breakdown(self, location_id: int) -> Tuple[str, float, float]:
        """
        Legacy helper (percentages) kept for compatibility.
        """
        kind = self.classify_location(location_id)
        sales, broker = self._rates(location_id, self.sell_client)
        return kind, sales * 100.0, broker * 100.0