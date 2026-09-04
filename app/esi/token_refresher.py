# FILE: app/esi/token_refresher.py
# VERSION: 1.0.0

import logging
import requests

from app.esi.sso_config import ESI_TOKEN_URL, ESI_CLIENT_ID

logger = logging.getLogger("app.esi.token_refresher")


def refresh_access_token(refresh_token: str) -> dict:
    """
    Exchanges a refresh token for a new access token.
    
    Returns a dict containing at least 'access_token' and 'refresh_token'.
    """
    logger.debug("Requesting new access token using refresh token")
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": ESI_CLIENT_ID,
    }
    
    resp = requests.post(ESI_TOKEN_URL, data=data)
    resp.raise_for_status()
    token_data = resp.json()
    
    # EVE SSO refresh response doesn't always include a new refresh token.
    # If it doesn't, we keep the old one.
    if "refresh_token" not in token_data:
        token_data["refresh_token"] = refresh_token
        
    logger.debug("Token refresh successful")
    return token_data