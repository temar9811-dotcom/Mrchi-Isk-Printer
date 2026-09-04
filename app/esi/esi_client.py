# FILE: app/esi/esi_client.py
# VERSION: 1.3.0

import time
import logging
import requests
from typing import Optional, Any, Dict, Callable, List

from app.models.character import Character
from app.esi.token_decoder import decode_jwt_payload
from app.esi.token_refresher import refresh_access_token

logger = logging.getLogger("app.esi.esi_client")

ESI_BASE_URL = "https://esi.evetech.net/latest"


class EsiClient:
    """
    Handles authenticated requests to the EVE ESI API.
    """

    def __init__(
        self,
        character: Character,
        on_token_refresh: Optional[Callable[[Character], None]] = None
    ):
        self.character = character
        self.on_token_refresh = on_token_refresh
        self.session = requests.Session()

    def _is_token_expired(self) -> bool:
        if not self.character.esi_access_token:
            return True
        try:
            payload = decode_jwt_payload(self.character.esi_access_token)
            exp = payload.get("exp", 0)
            return time.time() > (exp - 60)
        except Exception:
            logger.warning("Failed to decode access token")
            return True

    def _ensure_valid_token(self) -> bool:
        if not self._is_token_expired():
            return True
        logger.info("Access token expired. Refreshing...")
        if not self.character.esi_refresh_token:
            logger.error("No refresh token for %s", self.character.character_name)
            return False
        try:
            token_data = refresh_access_token(self.character.esi_refresh_token)
            self.character.esi_access_token = token_data["access_token"]
            self.character.esi_refresh_token = token_data["refresh_token"]
            if self.on_token_refresh:
                self.on_token_refresh(self.character)
            logger.info("Token refreshed for %s", self.character.character_name)
            return True
        except Exception:
            logger.exception("Failed to refresh token")
            return False

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.character.esi_access_token}",
            "Accept": "application/json",
        }

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        if not self._ensure_valid_token():
            raise PermissionError("Cannot authenticate with ESI.")
        url = f"{ESI_BASE_URL}{endpoint}"
        logger.debug("ESI GET %s", endpoint)
        resp = self.session.get(url, headers=self._get_headers(), params=params)
        if resp.status_code == 401:
            logger.warning("401 from ESI. Forcing refresh...")
            self.character.esi_access_token = ""
            if not self._ensure_valid_token():
                resp.raise_for_status()
            resp = self.session.get(url, headers=self._get_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    # --- Character endpoints ---
    def get_character_online(self) -> Dict:
        return self.get(f"/characters/{self.character.character_id}/online/")

    def get_character_location(self) -> Dict:
        return self.get(f"/characters/{self.character.character_id}/location/")

    def get_character_ship(self) -> Dict:
        return self.get(f"/characters/{self.character.character_id}/ship/")

    def get_character_skills(self) -> Dict:
        return self.get(f"/characters/{self.character.character_id}/skills/")

    # --- PI endpoints ---
    def get_character_planets(self) -> List[Dict]:
        return self.get(f"/characters/{self.character.character_id}/planets/")

    def get_planet_details(self, planet_id: int) -> Dict:
        return self.get(
            f"/characters/{self.character.character_id}/planets/{planet_id}/"
        )

    # --- Wallet endpoints ---
    def get_wallet_balance(self) -> float:
        return float(
            self.get(f"/characters/{self.character.character_id}/wallet/")
        )

    def get_wallet_transactions(self, page: int = 1) -> List[Dict]:
        return self.get(
            f"/characters/{self.character.character_id}/wallet/transactions/",
            params={"page": page},
        )

    # --- Contract endpoints ---
    def get_contracts(self, page: int = 1) -> List[Dict]:
        return self.get(
            f"/characters/{self.character.character_id}/contracts/",
            params={"page": page},
        )

    def get_contract_items(self, contract_id: int) -> List[Dict]:
        return self.get(
            f"/characters/{self.character.character_id}/contracts/{contract_id}/items/"
        )