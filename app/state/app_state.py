# FILE: app/state/app_state.py
# VERSION: 1.8.0

import logging
from typing import List, Optional

from PySide6.QtCore import QObject, Signal

from app.db.database import Database
from app.db.characters_repository import CharactersRepository
from app.models.character import Character
from app.settings.app_settings import AppSettings
from app.settings.settings_repository import SettingsRepository
from app.esi.login_worker import LoginWorker
from app.esi.esi_client import EsiClient
from app.esi.universe_resolver import UniverseResolver


class AppState(QObject):
    characters_changed = Signal()
    selected_character_changed = Signal(object)
    settings_changed = Signal()
    login_started = Signal()
    login_finished = Signal(str, str)
    login_url_ready = Signal(str)

    def __init__(
        self,
        db: Database,
        settings_repo: SettingsRepository,
    ):
        super().__init__()
        self.logger = logging.getLogger("app.state")
        self.db = db
        self.settings_repo = settings_repo
        self.characters_repo = CharactersRepository(db)
        self.universe_resolver = UniverseResolver(db)

        self.settings: AppSettings = settings_repo.load_app_settings()
        self.characters: List[Character] = []
        self.selected_character: Optional[Character] = None
        self.login_worker: Optional[LoginWorker] = None

        self.logger.debug("AppState initialized")

    def load_characters(self) -> None:
        selected_id = None
        if self.selected_character is not None:
            selected_id = self.selected_character.character_id
        self.characters = self.characters_repo.get_all_characters()
        self.characters_changed.emit()
        if selected_id is not None:
            self.select_character_by_id(selected_id)
        else:
            self.set_selected_character(None)

    def select_character_by_id(self, character_id: int) -> None:
        for character in self.characters:
            if character.character_id == character_id:
                self.set_selected_character(character)
                return
        self.set_selected_character(None)

    def set_selected_character(self, character: Optional[Character]) -> None:
        self.selected_character = character
        self.selected_character_changed.emit(character)

    def get_character(self, character_id: Optional[int]) -> Optional[Character]:
        if character_id is None:
            return None
        return next(
            (c for c in self.characters if c.character_id == character_id), None
        )

    def get_primary_character(self) -> Optional[Character]:
        char = self.get_character(self.settings.primary_character_id)
        if char is not None:
            return char
        # Fallback: first character with a refresh token
        return next((c for c in self.characters if c.esi_refresh_token), None)

    def get_primary_client(self) -> Optional[EsiClient]:
        char = self.get_primary_character()
        if char is None:
            return None
        return self.get_esi_client(char)

    def get_primary_token(self) -> Optional[str]:
        client = self.get_primary_client()
        if client is None:
            return None
        if client._ensure_valid_token():
            return client.character.esi_access_token
        return None

    def add_test_character(self) -> None:
        next_id = max((c.character_id for c in self.characters), default=0) + 1
        character = Character(
            character_id=next_id,
            character_name=f"Test Pilot {next_id}",
            notes="Created by Debug > Add test character",
        )
        self.characters_repo.add_character(character)
        self.load_characters()
        self.select_character_by_id(next_id)

    def start_login_flow(self) -> None:
        if self.login_worker is not None and self.login_worker.isRunning():
            self.logger.warning("Login flow already in progress")
            return

        self.logger.info("Starting ESI login flow from AppState")
        self.login_started.emit()

        self.login_worker = LoginWorker()
        self.login_worker.auth_url_ready.connect(self.login_url_ready)
        self.login_worker.success.connect(self._on_login_success)
        self.login_worker.error.connect(self._on_login_error)
        self.login_worker.finished.connect(self._on_login_worker_finished)
        self.login_worker.start()

    def cancel_login_flow(self) -> None:
        if self.login_worker is not None and self.login_worker.isRunning():
            self.logger.info("Cancelling login flow")
            self.login_worker.cancel()
        else:
            self.logger.debug("cancel_login_flow called with no running worker")

    def _on_login_success(self, data: dict) -> None:
        char_id = data["character_id"]
        char_name = data["character_name"]
        character = Character(
            character_id=char_id,
            character_name=char_name,
            esi_access_token=data["access_token"],
            esi_refresh_token=data["refresh_token"],
            notes="Added via EVE SSO",
        )
        self.characters_repo.add_character(character)
        self.load_characters()
        self.select_character_by_id(char_id)
        self.db.log_debug_event("auth", f"Character added: {char_name}")
        self.login_finished.emit(char_name, "Login successful.")

    def _on_login_error(self, error_msg: str) -> None:
        self.logger.error("Login flow failed: %s", error_msg)
        self.login_finished.emit("", f"Login failed: {error_msg}")

    def _on_login_worker_finished(self) -> None:
        self.login_worker = None

    def get_esi_client(self, character: Optional[Character] = None) -> Optional[EsiClient]:
        if character is None:
            character = self.selected_character
        if character is None:
            return None
        return EsiClient(character, on_token_refresh=self._on_token_refreshed)

    def get_universe_resolver(self) -> UniverseResolver:
        return self.universe_resolver

    def _on_token_refreshed(self, character: Character) -> None:
        self.logger.info("Saving refreshed token for %s", character.character_name)
        self.characters_repo.add_character(character)
        self.db.log_debug_event("auth", f"Token refreshed for {character.character_name}")

    def reload_settings(self) -> None:
        self.settings = self.settings_repo.load_app_settings()
        self.settings_changed.emit()

    def save_settings(self) -> None:
        self.settings_repo.save_app_settings(self.settings)
        self.settings_changed.emit()