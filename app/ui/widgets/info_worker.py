# FILE: app/ui/widgets/info_worker.py
# VERSION: 1.1.0

import logging

from PySide6.QtCore import QThread, Signal

from app.esi.esi_client import EsiClient
from app.esi.universe_resolver import UniverseResolver


class CharacterInfoWorker(QThread):
    """
    Fetches live character data from ESI and resolves IDs to names.
    """

    info_fetched = Signal(dict)
    error = Signal(str)

    def __init__(self, client: EsiClient, resolver: UniverseResolver):
        super().__init__()
        self.client = client
        self.resolver = resolver
        self.logger = logging.getLogger("app.ui.widgets.info_worker")

    def run(self):
        try:
            self.logger.debug("Starting character info fetch")

            online = self.client.get_character_online()
            location = self.client.get_character_location()
            ship = self.client.get_character_ship()

            # Resolve location names
            system_id = location.get("solar_system_id")
            station_id = location.get("station_id")
            structure_id = location.get("structure_id")

            system_name = ""
            station_name = ""

            if system_id:
                system_name = self.resolver.resolve_system(system_id)

            if station_id:
                station_name = self.resolver.resolve_station(station_id)
            elif structure_id:
                token = self.client.character.esi_access_token
                station_name = self.resolver.resolve_structure(structure_id, token)

            # Resolve ship type name
            ship_type_id = ship.get("ship_type_id")
            ship_name = ""
            if ship_type_id:
                ship_name = self.resolver.resolve_type(ship_type_id)

            self.logger.info(
                "Resolved: system=%s station=%s ship=%s",
                system_name, station_name, ship_name,
            )

            self.info_fetched.emit({
                "online": online,
                "location": location,
                "ship": ship,
                "system_name": system_name,
                "station_name": station_name,
                "ship_name": ship_name,
            })

        except Exception as exc:
            self.logger.exception("Character info fetch failed")
            self.error.emit(str(exc))