# FILE: app/esi/auth_flow.py
# VERSION: 1.3.0

import logging
import urllib.parse
import webbrowser
import requests
from typing import Callable, Optional

from app.esi.sso_config import (
    ESI_CLIENT_ID,
    ESI_AUTH_URL,
    ESI_TOKEN_URL,
    ESI_REDIRECT_URI,
)
from app.esi.scopes import get_scope_list_string
from app.esi.pkce import generate_pkce, generate_state
from app.esi.auth_server import run_server
from app.esi.token_decoder import decode_jwt_payload

logger = logging.getLogger("app.esi.auth_flow")


def perform_login_flow(
    stop_event=None,
    on_url: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Execute the full PKCE login flow.
    """
    logger.info("Starting ESI login flow")

    code_verifier, code_challenge = generate_pkce()
    state = generate_state()
    scope_str = get_scope_list_string()

    params = {
        "response_type": "code",
        "redirect_uri": ESI_REDIRECT_URI,
        "client_id": ESI_CLIENT_ID,
        "scope": scope_str,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = f"{ESI_AUTH_URL}?{urllib.parse.urlencode(params)}"

    if on_url is not None:
        try:
            on_url(auth_url)
        except Exception:
            logger.exception("on_url callback failed")

    logger.debug("Opening browser for EVE SSO login")
    webbrowser.open(auth_url)

    logger.debug("Waiting for local callback on port 8635...")
    auth_code, returned_state = run_server(
        8635,
        timeout=120,
        stop_event=stop_event,
    )

    if returned_state != state:
        raise ValueError("State mismatch! Possible CSRF attack.")
    if not auth_code:
        raise ValueError("No auth code received from EVE SSO.")

    logger.debug("Exchanging auth code for tokens")

    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "client_id": ESI_CLIENT_ID,
        "code_verifier": code_verifier,
    }

    resp = requests.post(ESI_TOKEN_URL, data=data)
    resp.raise_for_status()
    token_data = resp.json()

    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]

    payload = decode_jwt_payload(access_token)
    sub = payload["sub"]
    char_id = int(sub.split(":")[-1])
    char_name = payload["name"]

    logger.info("Login successful for character: %s (%s)", char_name, char_id)

    return {
        "character_id": char_id,
        "character_name": char_name,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }