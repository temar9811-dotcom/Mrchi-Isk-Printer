# FILE: app/settings/settings_repository.py
# VERSION: 1.0.0

import json
import logging
from typing import Optional

from app.db.database import Database
from app.settings.app_settings import AppSettings, SETTINGS_JSON_KEY


class SettingsRepository:
    """
    Reads and writes application settings from the SQLite database.
    """

    def __init__(self, db: Database):
        self.db = db
        self.logger = logging.getLogger("app.settings.repository")

    def get_setting(
        self,
        key: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get a raw string setting from the database.
        """
        row = self.db.query_one(
            """
            SELECT value
            FROM settings
            WHERE key = ?
            """,
            (key,),
        )

        if row is None:
            self.logger.debug("Setting not found: key=%s", key)
            return default

        return row["value"]

    def set_setting(self, key: str, value: str) -> None:
        """
        Insert or update a raw string setting in the database.
        """
        self.logger.debug(
            "Saving setting: key=%s value_length=%s",
            key,
            len(value),
        )

        self.db.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                updated_at=CURRENT_TIMESTAMP
            """,
            (key, value),
        )

    def load_app_settings(self) -> AppSettings:
        """
        Load the main application settings.

        If no settings exist yet, return defaults.
        If settings are corrupt, log the error and return defaults.
        """
        raw = self.get_setting(SETTINGS_JSON_KEY)

        if raw is None:
            self.logger.info("No saved settings found. Using defaults.")
            return AppSettings()

        try:
            data = json.loads(raw)
            settings = AppSettings.from_dict(data)
            self.logger.info("Application settings loaded from database.")
            return settings
        except Exception:
            self.logger.exception(
                "Failed to parse saved application settings. "
                "Falling back to defaults."
            )
            return AppSettings()

    def save_app_settings(self, settings: AppSettings) -> None:
        """
        Save the main application settings as JSON.
        """
        payload = json.dumps(
            settings.to_dict(),
            indent=2,
            sort_keys=True,
        )

        self.set_setting(SETTINGS_JSON_KEY, payload)
        self.logger.info("Application settings saved to database.")