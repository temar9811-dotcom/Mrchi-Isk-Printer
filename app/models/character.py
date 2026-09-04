# FILE: app/models/character.py
# VERSION: 1.0.0

from dataclasses import dataclass
from typing import Optional


@dataclass
class Character:
    """
    Basic character record.

    Later this will connect into ESI auth, tokens, PI data, wallet data,
    and market character selection.
    """

    character_id: int
    character_name: str
    added_at: str = ""
    esi_refresh_token: Optional[str] = None
    esi_access_token: Optional[str] = None
    esi_token_expires_at: Optional[str] = None
    notes: str = ""