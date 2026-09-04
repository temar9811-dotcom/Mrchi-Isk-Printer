# FILE: app/services/pi_optimizer.py
# VERSION: 1.1.0

import logging
from typing import Dict, List

from app.esi.esi_client import EsiClient
from app.esi.market_service import MarketService
from app.esi.universe_resolver import UniverseResolver
from app.models.pi_colony import PiColony
from app.models.trade_batch import PiBatchSuggestion

logger = logging.getLogger("app.services.pi_optimizer")

# Minimum stored value before a collection batch is worth suggesting.
MIN_BATCH_VALUE_ISK = 1_000_000


class PiOptimizer:
    """
    Evaluates current PI colonies and suggests collection/haul batches.

    IMPORTANT: This optimizer never suggests restarting or overhauling
    extractors. It only reports on what is worth collecting and selling.
    """

    def __init__(
        self,
        client: EsiClient,
        market: MarketService,
        resolver: UniverseResolver,
        sell_region: int,
        include_raws: bool,
    ):
        self.client = client
        self.market = market
        self.resolver = resolver
        self.sell_region = sell_region
        self.include_raws = include_raws

    def evaluate_colony(self, colony: PiColony) -> List[PiBatchSuggestion]:
        """
        Value up goods stored on one planet and suggest a haul batch.
        """
        suggestions: List[PiBatchSuggestion] = []

        try:
            raw = self.client.get_planet_details(colony.planet_id)
        except Exception as exc:
            logger.warning(
                "Failed to fetch colony detail for %s: %s",
                colony.planet_id,
                exc,
            )
            return suggestions

        # Accumulate stored goods. Contents sitting on extractor pins
        # are treated as raws (P0). Everything else is processed goods.
        goods: Dict[int, Dict] = {}

        for pin in raw.get("pins", []):
            is_extractor = "extractor_details" in pin

            for content in pin.get("contents", []):
                type_id = content.get("type_id", 0)
                amount = content.get("amount", 0)

                if not type_id or amount <= 0:
                    continue

                entry = goods.setdefault(
                    type_id, {"amount": 0, "raw": False}
                )
                entry["amount"] += amount

                if is_extractor:
                    entry["raw"] = True

        logger.debug(
            "Colony %s: %s distinct stored goods (include_raws=%s)",
            colony.planet_id,
            len(goods),
            self.include_raws,
        )

        valued = []
        total_value = 0.0
        total_volume = 0.0

        for type_id, entry in goods.items():
            if entry["raw"] and not self.include_raws:
                continue

            try:
                price = self.market.get_best_sell_price(
                    self.sell_region, type_id
                )
                info = self.market.get_type_info(type_id)
            except Exception as exc:
                logger.warning("Failed to price type %s: %s", type_id, exc)
                continue

            if price <= 0:
                continue

            value = price * entry["amount"]
            volume = (info.volume or 0.0) * entry["amount"]

            valued.append(
                {
                    "name": info.name or f"Type {type_id}",
                    "amount": entry["amount"],
                    "value": value,
                    "volume": volume,
                    "raw": entry["raw"],
                }
            )

            total_value += value
            total_volume += volume

        if total_value < MIN_BATCH_VALUE_ISK:
            logger.debug(
                "Colony %s stored value %s below threshold, no suggestion",
                colony.planet_id,
                total_value,
            )
            return suggestions

        valued.sort(key=lambda v: v["value"], reverse=True)

        lines = [
            f"{v['name']} x{v['amount']:,} ≈ {v['value']:,.0f} ISK"
            + (" (raw)" if v["raw"] else "")
            for v in valued[:4]
        ]

        suggestions.append(
            PiBatchSuggestion(
                planet_name=colony.display_name,
                action="Collection / Haul Batch",
                estimated_value=total_value,
                estimated_volume=total_volume,
                details=(
                    " | ".join(lines)
                    + f" | est volume {total_volume:,.0f} m3"
                ),
            )
        )

        logger.info(
            "Colony %s: suggested haul batch worth %s ISK",
            colony.planet_id,
            total_value,
        )

        return suggestions