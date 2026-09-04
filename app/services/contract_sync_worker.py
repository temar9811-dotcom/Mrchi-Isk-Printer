# FILE: app/services/contract_sync_worker.py
# VERSION: 1.0.0

import logging
from typing import List

from PySide6.QtCore import QThread, Signal

from app.esi.contract_service import ContractService


class ContractSyncWorker(QThread):
    finished_ok = Signal(list)
    error = Signal(str)

    def __init__(self, app_state, character_ids: List[int]):
        super().__init__()
        self.app_state = app_state
        self.character_ids = character_ids
        self.logger = logging.getLogger("app.services.contract_sync_worker")

    def run(self):
        messages: List[str] = []
        try:
            for cid in self.character_ids:
                char = self.app_state.get_character(cid)
                if char is None or not char.esi_refresh_token:
                    messages.append(f"Char {cid}: no token, skipped.")
                    continue
                client = self.app_state.get_esi_client(char)
                if client is None:
                    messages.append(f"{char.character_name}: no client.")
                    continue
                service = ContractService(self.app_state.db, client)
                summary = service.sync()
                messages.append(
                    f"{char.character_name}: {summary['contracts']} contracts."
                )
            self.finished_ok.emit(messages)
        except Exception as exc:
            self.logger.exception("Contract sync failed")
            self.error.emit(str(exc))