# FILE: app/ui/widgets/pi_worker.py
# VERSION: 1.1.0

import logging
from dataclasses import asdict

from PySide6.QtCore import QThread, Signal

from app.db.database import Database
from app.db.esi_cache_repository import EsiCacheRepository
from app.esi.esi_client import EsiClient
from app.esi.universe_resolver import UniverseResolver
from app.models.pi_colony import PiColony


class PiDataWorker(QThread):
    """
    Fetches PI planets for a character.

    cache_only=True  -> read from esi_cache only (instant).
    cache_only=False -> pull from ESI and store in esi_cache.
    """

    data_fetched = Signal(list)
    cache_empty = Signal()
    error = Signal(str)

    def __init__(self, client: EsiClient, resolver: UniverseResolver,
                 db: Database, cache_only: bool = False):
        super().__init__()
        self.client = client
        self.resolver = resolver
        self.cache = EsiCacheRepository(db)
        self.cache_only = cache_only
        self.logger = logging.getLogger("app.ui.widgets.pi_worker")

    def run(self):
        char_id = self.client.character.character_id
        key = f"pi:planets:{char_id}"

        try:
            if self.cache_only:
                payload, _ = self.cache.get(key)
                if payload is None:
                    self.logger.info("No cached PI planets for %s", char_id)
                    self.cache_empty.emit()
                    return
                colonies = [PiColony(**c) for c in payload]
                self.logger.info("PI planets from cache: %s", len(colonies))
                self.data_fetched.emit(colonies)
                return

            raw_planets = self.client.get_character_planets()
            colonies = []
            for raw in raw_planets:
                planet_id = raw.get("planet_id", 0)
                system_id = raw.get("solar_system_id", 0)
                colonies.append(PiColony(
                    planet_id=planet_id,
                    planet_type=raw.get("planet_type", "unknown"),
                    solar_system_id=system_id,
                    num_pins=raw.get("num_pins", 0),
                    upgrade_level=raw.get("upgrade_level", 0),
                    last_update=raw.get("last_update", ""),
                    owner_id=raw.get("owner_id", 0),
                    planet_name=self.resolver.resolve_planet(planet_id),
                    system_name=self.resolver.resolve_system(system_id),
                ))

            self.cache.set(key, [asdict(c) for c in colonies])
            self.logger.info("PI planets from ESI: %s", len(colonies))
            self.data_fetched.emit(colonies)
        except Exception as exc:
            self.logger.exception("PI data fetch failed")
            self.error.emit(str(exc))