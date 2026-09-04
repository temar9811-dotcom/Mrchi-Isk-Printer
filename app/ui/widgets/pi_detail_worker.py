# FILE: app/ui/widgets/pi_detail_worker.py
# VERSION: 1.1.0

import logging
from dataclasses import asdict
from typing import Dict

from PySide6.QtCore import QThread, Signal

from app.db.database import Database
from app.db.esi_cache_repository import EsiCacheRepository
from app.esi.esi_client import EsiClient
from app.esi.universe_resolver import UniverseResolver
from app.models.pi_colony import PiColony
from app.models.pi_colony_detail import (
    PiColonyDetail,
    PiPin,
    PiPinContent,
    PiRoute,
)


def _categorize(pin_raw: Dict, type_name: str) -> str:
    if "extractor_details" in pin_raw:
        return "Extractors"
    if "factory_details" in pin_raw or pin_raw.get("schematic_id"):
        return "Factories"
    lowered = type_name.lower()
    if "command center" in lowered:
        return "Command Center"
    if "launcher" in lowered:
        return "Launchers"
    if "storage" in lowered:
        return "Storage"
    return "Other"


def _detail_from_dict(d: Dict) -> PiColonyDetail:
    pins = []
    for p in d.get("pins", []):
        contents = [PiPinContent(**cc) for cc in p.get("contents", [])]
        clean = dict(p)
        clean["contents"] = contents
        pins.append(PiPin(**clean))
    routes = [PiRoute(**r) for r in d.get("routes", [])]
    clean = dict(d)
    clean["pins"] = pins
    clean["routes"] = routes
    return PiColonyDetail(**clean)


class PiDetailWorker(QThread):
    """
    Fetches one colony layout. cache_only reads esi_cache only.
    """

    detail_fetched = Signal(object)
    cache_empty = Signal()
    error = Signal(str)

    def __init__(self, client: EsiClient, resolver: UniverseResolver,
                 db: Database, colony: PiColony, cache_only: bool = False):
        super().__init__()
        self.client = client
        self.resolver = resolver
        self.cache = EsiCacheRepository(db)
        self.colony = colony
        self.cache_only = cache_only
        self.logger = logging.getLogger("app.ui.widgets.pi_detail_worker")

    def run(self):
        char_id = self.client.character.character_id
        key = f"pi:planet:{char_id}:{self.colony.planet_id}"

        try:
            if self.cache_only:
                payload, _ = self.cache.get(key)
                if payload is None:
                    self.cache_empty.emit()
                    return
                self.detail_fetched.emit(_detail_from_dict(payload))
                return

            raw = self.client.get_planet_details(self.colony.planet_id)

            detail = PiColonyDetail(
                planet_id=self.colony.planet_id,
                planet_name=self.colony.display_name,
                links_count=len(raw.get("links", [])),
            )

            pin_names = {}

            for raw_pin in raw.get("pins", []):
                pin = self._build_pin(raw_pin)
                pin_names[pin.pin_id] = pin.type_name
                detail.pins.append(pin)

            for raw_route in raw.get("routes", []):
                route = PiRoute(
                    source_pin_id=raw_route.get("source_pin_id", 0),
                    destination_pin_id=raw_route.get("destination_pin_id", 0),
                    quantity=raw_route.get("quantity", 0),
                    content_type_id=raw_route.get("content_type_id", 0),
                )
                if route.content_type_id:
                    route.content_type_name = self.resolver.resolve_type(
                        route.content_type_id
                    )
                route.source_name = pin_names.get(
                    route.source_pin_id, f"Pin {route.source_pin_id}"
                )
                route.destination_name = pin_names.get(
                    route.destination_pin_id, f"Pin {route.destination_pin_id}"
                )
                detail.routes.append(route)

            self.cache.set(key, asdict(detail))
            self.logger.info(
                "Colony detail from ESI: pins=%s routes=%s",
                len(detail.pins), len(detail.routes),
            )
            self.detail_fetched.emit(detail)
        except Exception as exc:
            self.logger.exception("Colony detail fetch failed")
            self.error.emit(str(exc))

    def _build_pin(self, raw_pin: Dict) -> PiPin:
        type_id = raw_pin.get("type_id", 0)
        type_name = self.resolver.resolve_type(type_id)

        pin = PiPin(
            pin_id=raw_pin.get("pin_id", 0),
            type_id=type_id,
            type_name=type_name,
            upgrade_level=raw_pin.get("upgrade_level", 0),
            schematic_id=raw_pin.get("schematic_id"),
            install_time=raw_pin.get("install_time", ""),
            last_cycle_start=raw_pin.get("last_cycle_start", ""),
            expiry_time=raw_pin.get("expiry_time", ""),
            category=_categorize(raw_pin, type_name),
        )

        if pin.schematic_id:
            pin.schematic_name = self.resolver.resolve_schematic(pin.schematic_id)

        extractor = raw_pin.get("extractor_details")
        if extractor:
            pin.head_count = len(extractor.get("heads", []))
            pin.cycle_time_seconds = extractor.get("cycle_time", 0)
            pin.qty_per_cycle = extractor.get("qty_per_cycle", 0)
            pin.product_type_id = extractor.get("product_type_id")
            if pin.product_type_id:
                pin.product_type_name = self.resolver.resolve_type(
                    pin.product_type_id
                )

        for raw_content in raw_pin.get("contents", []):
            content = PiPinContent(
                type_id=raw_content.get("type_id", 0),
                amount=raw_content.get("amount", 0),
            )
            content.type_name = self.resolver.resolve_type(content.type_id)
            pin.contents.append(content)

        return pin