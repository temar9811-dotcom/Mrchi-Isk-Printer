# FILE: app/db/characters_repository.py
# VERSION: 1.0.0

import logging
from typing import List, Optional

from app.db.database import Database
from app.models.character import Character


class CharactersRepository:
    """
    Handles character persistence in SQLite.
    """

    def __init__(self, db: Database):
        self.db = db
        self.logger = logging.getLogger("app.db.characters_repository")

    def add_character(self, character: Character) -> None:
        """
        Insert a character, or update it if the character_id already exists.
        """
        self.logger.debug(
            "Upserting character: id=%s name=%s",
            character.character_id,
            character.character_name,
        )

        self.db.execute(
            """
            INSERT INTO characters (
                character_id,
                character_name,
                esi_refresh_token,
                esi_access_token,
                esi_token_expires_at,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(character_id) DO UPDATE SET
                character_name=excluded.character_name,
                esi_refresh_token=excluded.esi_refresh_token,
                esi_access_token=excluded.esi_access_token,
                esi_token_expires_at=excluded.esi_token_expires_at,
                notes=excluded.notes
            """,
            (
                character.character_id,
                character.character_name,
                character.esi_refresh_token,
                character.esi_access_token,
                character.esi_token_expires_at,
                character.notes,
            ),
        )

    def get_all_characters(self) -> List[Character]:
        """
        Return all added characters ordered by name.
        """
        rows = self.db.query(
            """
            SELECT
                character_id,
                character_name,
                added_at,
                esi_refresh_token,
                esi_access_token,
                esi_token_expires_at,
                notes
            FROM characters
            ORDER BY character_name
            """
        )

        characters = [self._row_to_character(row) for row in rows]

        self.logger.debug(
            "Loaded %s characters from database",
            len(characters),
        )

        return characters

    def get_character(self, character_id: int) -> Optional[Character]:
        """
        Return one character by character_id.
        """
        row = self.db.query_one(
            """
            SELECT
                character_id,
                character_name,
                added_at,
                esi_refresh_token,
                esi_access_token,
                esi_token_expires_at,
                notes
            FROM characters
            WHERE character_id = ?
            """,
            (character_id,),
        )

        if row is None:
            self.logger.debug(
                "Character not found: character_id=%s",
                character_id,
            )
            return None

        return self._row_to_character(row)

    def delete_character(self, character_id: int) -> None:
        """
        Delete a character from the database.
        """
        self.logger.debug(
            "Deleting character: character_id=%s",
            character_id,
        )

        self.db.execute(
            """
            DELETE FROM characters
            WHERE character_id = ?
            """,
            (character_id,),
        )

    def _row_to_character(self, row) -> Character:
        """
        Convert a sqlite3.Row into a Character dataclass.
        """
        return Character(
            character_id=row["character_id"],
            character_name=row["character_name"],
            added_at=row["added_at"] or "",
            esi_refresh_token=row["esi_refresh_token"],
            esi_access_token=row["esi_access_token"],
            esi_token_expires_at=row["esi_token_expires_at"],
            notes=row["notes"] or "",
        )