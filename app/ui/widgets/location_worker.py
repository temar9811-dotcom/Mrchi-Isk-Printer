# FILE: app/ui/widgets/location_worker.py
# VERSION: 1.0.0

import logging

from PySide6.QtCore import QThread, Signal

from app.esi.esi_client import EsiClient


class LocationFetchWorker(QThread):
    """
    Fetches the current location of a character in the background
    so the settings UI never freezes.
    """

    location_fetched = Signal(dict)
    error = Signal(str)

    def __init__(self, client: EsiClient):
        super().__init__()
        self.client = client
        self.logger = logging.getLogger("app.ui.widgets.location_worker")

    def run(self):
        try:
            loc = self.client.get_character_location()
            self.logger.debug("Location fetched: %s", loc)
            self.location_fetched.emit(loc)
        except Exception as exc:
            self.logger.exception("Location fetch failed")
            self.error.emit(str(exc))